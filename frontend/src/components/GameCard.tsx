import { useState } from 'react';
import type { GameResponse, ViewMode } from '../api/types';
import { PredictionColumn } from './PredictionColumn';
import { KalshiSection } from './KalshiSection';
import { LiveDetail } from './LiveDetail';
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

function formatInningOrdinal(inning: number): string {
  if (inning === 1) return '1st';
  if (inning === 2) return '2nd';
  if (inning === 3) return '3rd';
  return `${inning}th`;
}

function formatInningHalf(half: 'top' | 'bottom'): string {
  return half === 'top' ? 'Top' : 'Bot';
}

interface GameCardProps {
  game: GameResponse;
  viewMode: ViewMode | null;
}

export function GameCard({ game, viewMode }: GameCardProps) {
  const { home_team, away_team, prediction, game_status } = game;
  const [expanded, setExpanded] = useState(false);

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

      {/* Score row -- LIVE games only */}
      {game_status === 'LIVE' && game.live_score && (
        <>
          <div
            className={styles.scoreRow}
            role="button"
            tabIndex={0}
            aria-expanded={expanded}
            onClick={() => setExpanded(prev => !prev)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setExpanded(prev => !prev);
              }
            }}
          >
            <div className={styles.scoreText}>
              <span className={styles.scoreTeams}>
                {away_team} {game.live_score.away_score} - {home_team} {game.live_score.home_score}
              </span>
              <span className={styles.scoreInning}>
                {'\u00B7'} {formatInningHalf(game.live_score.inning_half)} {formatInningOrdinal(game.live_score.inning)} {'\u00B7'} {game.live_score.outs} out
              </span>
            </div>
            <span className={`${styles.expandChevron} ${expanded ? styles.expandChevronOpen : ''}`}>
              {'\u25BE'}
            </span>
          </div>
          {expanded && <LiveDetail liveScore={game.live_score} />}
        </>
      )}

      {/* Final score + outcome row -- FINAL games only */}
      {game_status === 'FINAL' && game.home_final_score !== null && (
        <div className={styles.finalRow}>
          <div className={styles.finalScoreText}>
            <span className={styles.scoreTeams}>
              {away_team} {game.away_final_score} - {home_team} {game.home_final_score}
            </span>
            <span className={styles.finalLabel}>Final</span>
          </div>
          {game.prediction_correct !== null && (
            <span className={game.prediction_correct ? styles.outcomeCorrect : styles.outcomeIncorrect}>
              {game.prediction_correct ? '\u2713' : '\u2717'}
            </span>
          )}
        </div>
      )}

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

      {/* Kalshi section -- absent for stub cards and future mode.
          Edge badge suppressed for LIVE/FINAL: pre-game betting window is
          closed and any stored Kalshi price may reflect in-game state. */}
      {hasPrediction && primary && viewMode !== 'future' && (
        <KalshiSection
          price={primary.kalshi_yes_price}
          edgeSignal={game_status === 'PRE_GAME' ? primary.edge_signal : null}
          edgeMagnitude={game_status === 'PRE_GAME' ? primary.edge_magnitude : null}
        />
      )}
    </div>
  );
}
