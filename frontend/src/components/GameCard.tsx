import type { GameResponse, ViewMode } from '../api/types';
import { PredictionColumn } from './PredictionColumn';
import { KalshiSection } from './KalshiSection';
import { SpBadge } from './SpBadge';
import { StatusBadge } from './StatusBadge';
import styles from './GameCard.module.css';

function formatGameTime(isoString: string | null): string {
  if (!isoString) return 'Time TBD';
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return 'Time TBD';
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      timeZone: 'America/New_York',
    }) + ' ET';
  } catch {
    return 'Time TBD';
  }
}

interface GameCardProps {
  game: GameResponse;
  viewMode: ViewMode | null;
}

export function GameCard({ game, viewMode }: GameCardProps) {
  const { home_team, away_team, prediction, game_status } = game;

  const pre_lineup = prediction?.pre_lineup ?? null;
  const post_lineup = prediction?.post_lineup ?? null;

  // Use the most relevant prediction for SP info and Kalshi data
  const primary = post_lineup ?? pre_lineup;
  const showWarning =
    post_lineup?.sp_may_have_changed === true ||
    pre_lineup?.sp_may_have_changed === true;

  const hasBothVersions = post_lineup !== null && pre_lineup !== null;
  const hasPrediction = prediction !== null;

  // SP name fallback: use prediction SP names, then schedule pitcher names
  const awaySpName = primary?.away_sp ?? game.away_probable_pitcher;
  const homeSpName = primary?.home_sp ?? game.home_probable_pitcher;
  const spStatus = primary?.prediction_status === 'tbd' ? 'tbd' : 'confirmed';

  return (
    <div className={styles.card}>
      {/* Amber warning strip for SP changes */}
      {showWarning && (
        <div className={styles.warningStrip}>
          SP assignment may have changed — confirmation pending
        </div>
      )}

      {/* Header row: teams + time + badge + SP names */}
      <div className={styles.headerRow}>
        <p className={styles.matchup}>
          {away_team} @ {home_team}
        </p>
        <p className={game.game_time ? styles.gameTime : styles.gameTimeTbd}>
          {formatGameTime(game.game_time)}
        </p>
        <div className={styles.statusBadge}>
          <StatusBadge status={game_status} />
        </div>
        {game.prediction_label === 'PRELIMINARY' && (
          <span className={styles.preliminaryBadge}>PRELIMINARY</span>
        )}
        <div className={styles.spRow}>
          {awaySpName ? (
            <SpBadge
              status={spStatus}
              name={awaySpName}
            />
          ) : (
            <SpBadge status="tbd" />
          )}
          <span>|</span>
          {homeSpName ? (
            <SpBadge
              status={spStatus}
              name={homeSpName}
            />
          ) : (
            <SpBadge status="tbd" />
          )}
        </div>
      </div>

      {/* Prediction body -- absent for stub cards and future mode */}
      {hasPrediction && viewMode !== 'future' && (
        <div className={styles.predictionBody}>
          {hasBothVersions ? (
            <>
              <div className={styles.splitColumn}>
                <PredictionColumn
                  prediction={post_lineup}
                  isPrimary={true}
                  label="POST-LINEUP"
                />
              </div>
              <div className={styles.splitColumn}>
                <PredictionColumn
                  prediction={pre_lineup}
                  isPrimary={false}
                  label="PRE-LINEUP"
                />
              </div>
            </>
          ) : pre_lineup ? (
            <div className={styles.fullWidth}>
              <PredictionColumn
                prediction={pre_lineup}
                isPrimary={true}
                label="TEAM ONLY"
              />
            </div>
          ) : post_lineup ? (
            <div className={styles.fullWidth}>
              <PredictionColumn
                prediction={post_lineup}
                isPrimary={true}
                label="POST-LINEUP"
              />
            </div>
          ) : null}
        </div>
      )}

      {/* Kalshi section -- absent for stub cards and future mode */}
      {hasPrediction && primary && viewMode !== 'future' && (
        <KalshiSection
          price={primary.kalshi_yes_price}
          edgeSignal={primary.edge_signal}
          edgeMagnitude={primary.edge_magnitude}
        />
      )}
    </div>
  );
}
