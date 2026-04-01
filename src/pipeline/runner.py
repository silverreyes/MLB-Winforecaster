"""Main pipeline runner: orchestrates fetch -> features -> predict -> store.

Dispatches based on prediction_version:
  pre_lineup (10am ET):    TEAM_ONLY models, SP fields null, sp_uncertainty=True
  post_lineup (1pm ET):    SP_ENHANCED models for confirmed SPs, TEAM_ONLY fallback for TBD
  confirmation (5pm ET):   Full re-run, compare SPs to post_lineup, flag changes
"""
import logging
from datetime import date, datetime, timezone

from src.pipeline.live_features import LiveFeatureBuilder
from src.pipeline.inference import predict_game
from src.pipeline.db import (
    insert_prediction,
    mark_not_latest,
    get_post_lineup_prediction,
    insert_pipeline_run,
    update_pipeline_run,
)
from src.data.kalshi import fetch_kalshi_live_prices

logger = logging.getLogger(__name__)

EDGE_THRESHOLD = 0.05  # 5pp minimum divergence for edge signal


def compute_edge_signal(model_probs: dict[str, float], kalshi_price: float | None) -> str:
    """Compute edge signal from model average probability vs Kalshi price.

    Args:
        model_probs: {model_name: calibrated_prob} from predict_game.
        kalshi_price: Current Kalshi yes price (P(home_win)), or None.

    Returns:
        'BUY_YES', 'BUY_NO', or 'NO_EDGE'.
    """
    if not kalshi_price or kalshi_price <= 0 or not model_probs:
        return "NO_EDGE"
    avg_prob = sum(model_probs.values()) / len(model_probs)
    edge = avg_prob - kalshi_price
    if abs(edge) <= EDGE_THRESHOLD:
        return "NO_EDGE"
    return "BUY_YES" if edge > 0 else "BUY_NO"


def _build_kalshi_key(game_date_str: str, home_team: str, away_team: str) -> str:
    """Build Kalshi lookup key matching fetch_kalshi_live_prices format."""
    return f"{game_date_str}_{home_team}_{away_team}"


def run_pipeline(
    version: str,
    artifacts: dict,
    pool,
    feature_builder: LiveFeatureBuilder | None = None,
):
    """Run a single pipeline cycle for the given prediction version.

    Args:
        version: 'pre_lineup', 'post_lineup', or 'confirmation'.
        artifacts: All 6 loaded model artifacts from load_all_artifacts().
        pool: psycopg ConnectionPool.
        feature_builder: Optional pre-initialized LiveFeatureBuilder.
            If None, a new one will be created and initialized.
    """
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")

    # Log pipeline run start
    run_id = insert_pipeline_run(pool, version, today)
    logger.info(f"Pipeline run started: version={version}, run_id={run_id}, date={today_str}")

    try:
        # Initialize feature builder
        if feature_builder is None:
            feature_builder = LiveFeatureBuilder(pool=pool)
        feature_builder.initialize()

        # Fetch today's games
        games = feature_builder.get_today_games()
        logger.info(f"Found {len(games)} games for {today_str}")

        if not games:
            update_pipeline_run(pool, run_id, "success", 0)
            logger.info("No games found, pipeline run complete")
            return

        # Fetch Kalshi live prices (graceful degradation on failure)
        kalshi_prices = fetch_kalshi_live_prices()
        logger.info(f"Fetched {len(kalshi_prices)} Kalshi prices")

        games_processed = 0

        for game in games:
            try:
                _process_game(
                    game=game,
                    version=version,
                    artifacts=artifacts,
                    pool=pool,
                    feature_builder=feature_builder,
                    kalshi_prices=kalshi_prices,
                    today_str=today_str,
                )
                games_processed += 1
            except Exception as e:
                logger.error(
                    f"Error processing {game['home_team']} vs {game['away_team']}: {e}",
                    exc_info=True,
                )

        update_pipeline_run(pool, run_id, "success", games_processed)
        logger.info(f"Pipeline run complete: {games_processed}/{len(games)} games processed")

    except Exception as e:
        logger.error(f"Pipeline run failed: {e}", exc_info=True)
        update_pipeline_run(pool, run_id, "failed", 0, str(e))
        raise


def _process_game(
    game: dict,
    version: str,
    artifacts: dict,
    pool,
    feature_builder: LiveFeatureBuilder,
    kalshi_prices: dict[str, float],
    today_str: str,
):
    """Process a single game for the given pipeline version.

    Skips games that are already in progress or completed. Kalshi edge signals
    are only meaningful pre-game; once a game starts the market reflects live
    state and the signal is no longer actionable.
    """
    home_team = game["home_team"]
    away_team = game["away_team"]

    # Gate: skip any game that has already started or finished.
    # MLB Stats API status values for pre-game: Preview, Pre-Game, Scheduled,
    # Warmup, "", None.  Anything else (In Progress, Final, Game Over, etc.)
    # means the window for pre-game Kalshi betting has closed.
    PRE_GAME_STATUSES = {"Preview", "Pre-Game", "Scheduled", "Warmup", "", None}
    game_status = game.get("status")
    if game_status not in PRE_GAME_STATUSES:
        logger.info(
            f"Skipping {home_team} vs {away_team}: game already started (status={game_status!r})"
        )
        return

    kalshi_key = _build_kalshi_key(today_str, home_team, away_team)
    kalshi_price = kalshi_prices.get(kalshi_key)

    if version == "pre_lineup":
        _process_pre_lineup(game, artifacts, pool, feature_builder, kalshi_price, today_str)
    elif version == "post_lineup":
        _process_post_lineup(game, artifacts, pool, feature_builder, kalshi_price, today_str)
    elif version == "confirmation":
        _process_confirmation(game, artifacts, pool, feature_builder, kalshi_price, today_str)


def _process_pre_lineup(game, artifacts, pool, fb, kalshi_price, today_str):
    """Pre-lineup: TEAM_ONLY only, SP fields null, sp_uncertainty=True."""
    features = fb.build_features_for_game(game, "team_only")
    if features is None:
        logger.warning(f"Cannot build team_only features for {game['home_team']} vs {game['away_team']}")
        return

    probs = predict_game(artifacts, features, "team_only")
    if not probs:
        return

    edge_signal = compute_edge_signal(probs, kalshi_price)

    insert_prediction(pool, {
        "game_date": today_str,
        "home_team": game["home_team"],
        "away_team": game["away_team"],
        "prediction_version": "pre_lineup",
        "prediction_status": "tbd",
        "lr_prob": probs.get("lr"),
        "rf_prob": probs.get("rf"),
        "xgb_prob": probs.get("xgb"),
        "feature_set": "team_only",
        "home_sp": game.get("home_probable_pitcher"),
        "away_sp": game.get("away_probable_pitcher"),
        "sp_uncertainty": True,
        "sp_may_have_changed": False,
        "kalshi_yes_price": kalshi_price,
        "edge_signal": edge_signal,
        "is_latest": True,
        "game_id": game.get("game_id"),
    })


def _process_post_lineup(game, artifacts, pool, fb, kalshi_price, today_str):
    """Post-lineup: SP_ENHANCED if SPs confirmed, else TEAM_ONLY with sp_uncertainty."""
    if fb.sp_confirmed(game):
        # SPs confirmed: run SP_ENHANCED models
        features = fb.build_features_for_game(game, "sp_enhanced")
        if features is None:
            # Fallback to team_only if sp_enhanced feature build fails
            logger.warning(f"SP_ENHANCED features failed for {game['home_team']} vs {game['away_team']}, falling back to team_only")
            _insert_team_only_fallback(game, artifacts, pool, fb, kalshi_price, today_str, "post_lineup")
            return

        probs = predict_game(artifacts, features, "sp_enhanced")
        if not probs:
            logger.warning(
                f"SP_ENHANCED prediction yielded no probs for "
                f"{game['home_team']} vs {game['away_team']}, falling back to team_only"
            )
            _insert_team_only_fallback(game, artifacts, pool, fb, kalshi_price, today_str, "post_lineup")
            return

        edge_signal = compute_edge_signal(probs, kalshi_price)

        insert_prediction(pool, {
            "game_date": today_str,
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "prediction_version": "post_lineup",
            "prediction_status": "confirmed",
            "lr_prob": probs.get("lr"),
            "rf_prob": probs.get("rf"),
            "xgb_prob": probs.get("xgb"),
            "feature_set": "sp_enhanced",
            "home_sp": game.get("home_probable_pitcher"),
            "away_sp": game.get("away_probable_pitcher"),
            "sp_uncertainty": False,
            "sp_may_have_changed": False,
            "kalshi_yes_price": kalshi_price,
            "edge_signal": edge_signal,
            "is_latest": True,
            "game_id": game.get("game_id"),
        })
    else:
        # TBD starters: TEAM_ONLY only, do NOT insert as post_lineup (PIPE-07)
        # Insert as pre_lineup update instead -- the DB CHECK constraint prevents
        # post_lineup with non-confirmed status
        logger.info(f"SPs TBD for {game['home_team']} vs {game['away_team']}, skipping post_lineup")


def _insert_team_only_fallback(game, artifacts, pool, fb, kalshi_price, today_str, version):
    """Insert a TEAM_ONLY prediction when SP_ENHANCED fails or SPs are TBD."""
    features = fb.build_features_for_game(game, "team_only")
    if features is None:
        return

    probs = predict_game(artifacts, features, "team_only")
    if not probs:
        return

    edge_signal = compute_edge_signal(probs, kalshi_price)

    # Use pre_lineup version for TBD fallback (PIPE-07: no post_lineup without confirmed SPs)
    insert_prediction(pool, {
        "game_date": today_str,
        "home_team": game["home_team"],
        "away_team": game["away_team"],
        "prediction_version": "pre_lineup",
        "prediction_status": "tbd",
        "lr_prob": probs.get("lr"),
        "rf_prob": probs.get("rf"),
        "xgb_prob": probs.get("xgb"),
        "feature_set": "team_only",
        "home_sp": None,
        "away_sp": None,
        "sp_uncertainty": True,
        "sp_may_have_changed": False,
        "kalshi_yes_price": kalshi_price,
        "edge_signal": edge_signal,
        "is_latest": True,
        "game_id": game.get("game_id"),
    })


def _process_confirmation(game, artifacts, pool, fb, kalshi_price, today_str):
    """Confirmation: full re-run, compare SPs to post_lineup, flag changes."""
    home_sp = game.get("home_probable_pitcher")
    away_sp = game.get("away_probable_pitcher")

    # Get existing post_lineup prediction for comparison
    existing = get_post_lineup_prediction(pool, today_str, game["home_team"], game["away_team"])

    # Detect SP changes
    sp_changed = False
    if existing and (existing.get("home_sp") != home_sp or existing.get("away_sp") != away_sp):
        sp_changed = True
        # Mark old post_lineup row as not latest
        mark_not_latest(pool, today_str, game["home_team"], game["away_team"], "post_lineup")
        logger.info(
            f"SP change detected for {game['home_team']} vs {game['away_team']}: "
            f"was ({existing.get('home_sp')}, {existing.get('away_sp')}) -> "
            f"now ({home_sp}, {away_sp})"
        )

    # Run full prediction with current data
    if fb.sp_confirmed(game):
        features = fb.build_features_for_game(game, "sp_enhanced")
        if features is None:
            features = fb.build_features_for_game(game, "team_only")
            feature_set = "team_only"
            probs = predict_game(artifacts, features, "team_only") if features else {}
            status = "pending_sp"
        else:
            feature_set = "sp_enhanced"
            probs = predict_game(artifacts, features, "sp_enhanced")
            status = "confirmed"
    else:
        features = fb.build_features_for_game(game, "team_only")
        feature_set = "team_only"
        probs = predict_game(artifacts, features, "team_only") if features else {}
        status = "tbd"

    if not probs:
        return

    edge_signal = compute_edge_signal(probs, kalshi_price)

    insert_prediction(pool, {
        "game_date": today_str,
        "home_team": game["home_team"],
        "away_team": game["away_team"],
        "prediction_version": "confirmation",
        "prediction_status": status,
        "lr_prob": probs.get("lr"),
        "rf_prob": probs.get("rf"),
        "xgb_prob": probs.get("xgb"),
        "feature_set": feature_set,
        "home_sp": home_sp,
        "away_sp": away_sp,
        "sp_uncertainty": not fb.sp_confirmed(game),
        "sp_may_have_changed": sp_changed,
        "kalshi_yes_price": kalshi_price,
        "edge_signal": edge_signal,
        "is_latest": True,
        "game_id": game.get("game_id"),
    })
