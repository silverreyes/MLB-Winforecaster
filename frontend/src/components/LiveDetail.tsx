import type { LiveScoreData } from '../api/types';
import { BasesDiamond } from './BasesDiamond';
import styles from './LiveDetail.module.css';

interface LiveDetailProps {
  liveScore: LiveScoreData;
}

export function LiveDetail({ liveScore }: LiveDetailProps) {
  return (
    <div className={styles.expandedDetail} aria-label="Live game details">
      <div className={styles.diamondColumn}>
        <BasesDiamond
          runner_on_1b={liveScore.runner_on_1b}
          runner_on_2b={liveScore.runner_on_2b}
          runner_on_3b={liveScore.runner_on_3b}
        />
      </div>
      <div className={styles.infoColumn}>
        <div className={styles.countRow}>
          B: {liveScore.balls}  S: {liveScore.strikes}  O: {liveScore.outs}
        </div>
        <div className={styles.batterRow}>
          <span className={styles.batterName}>
            {liveScore.current_batter ?? '--'}
          </span>
          {liveScore.current_batter && liveScore.batter_avg && (
            <span className={styles.batterStats}>
              {liveScore.batter_avg} / {liveScore.batter_ops ?? '--'}
            </span>
          )}
        </div>
        {liveScore.on_deck_batter && (
          <div className={styles.batterRow}>
            <span className={styles.onDeckLabel}>On deck:</span>
            <span className={styles.onDeckName}>{liveScore.on_deck_batter}</span>
          </div>
        )}
      </div>
    </div>
  );
}
