import type { GameGroup } from '../api/types';
import { PredictionColumn } from './PredictionColumn';
import { KalshiSection } from './KalshiSection';
import { SpBadge } from './SpBadge';
import styles from './GameCard.module.css';

interface GameCardProps {
  game: GameGroup;
  isStale: boolean;
}

export function GameCard({ game }: GameCardProps) {
  const { home_team, away_team, pre_lineup, post_lineup } = game;

  // Use the most relevant prediction for SP info and Kalshi data
  const primary = post_lineup ?? pre_lineup;
  const showWarning =
    post_lineup?.sp_may_have_changed === true ||
    pre_lineup?.sp_may_have_changed === true;

  const hasBothVersions = post_lineup !== null && pre_lineup !== null;

  return (
    <div className={styles.card}>
      {/* Amber warning strip for SP changes */}
      {showWarning && (
        <div className={styles.warningStrip}>
          SP assignment may have changed — confirmation pending
        </div>
      )}

      {/* Header row: teams + SP names */}
      <div className={styles.headerRow}>
        <p className={styles.matchup}>
          {away_team} @ {home_team}
        </p>
        <div className={styles.spRow}>
          {primary?.away_sp ? (
            <SpBadge
              status={primary.prediction_status === 'tbd' ? 'tbd' : 'confirmed'}
              name={primary.away_sp}
            />
          ) : (
            <SpBadge status="tbd" />
          )}
          <span>|</span>
          {primary?.home_sp ? (
            <SpBadge
              status={primary.prediction_status === 'tbd' ? 'tbd' : 'confirmed'}
              name={primary.home_sp}
            />
          ) : (
            <SpBadge status="tbd" />
          )}
        </div>
      </div>

      {/* Prediction body */}
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

      {/* Kalshi section */}
      {primary && (
        <KalshiSection
          price={primary.kalshi_yes_price}
          edgeSignal={primary.edge_signal}
          edgeMagnitude={primary.edge_magnitude}
        />
      )}
    </div>
  );
}
