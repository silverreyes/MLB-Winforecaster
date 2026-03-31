import type { GameStatus } from '../api/types';
import styles from './StatusBadge.module.css';

const STATUS_CLASS_MAP: Record<GameStatus, string> = {
  PRE_GAME: styles.preGame,
  LIVE: styles.live,
  FINAL: styles.final,
  POSTPONED: styles.postponed,
};

const STATUS_DISPLAY: Record<GameStatus, string> = {
  PRE_GAME: 'PRE-GAME',
  LIVE: 'LIVE',
  FINAL: 'FINAL',
  POSTPONED: 'POSTPONED',
};

interface StatusBadgeProps {
  status: GameStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`${styles.badge} ${STATUS_CLASS_MAP[status]}`}>
      {STATUS_DISPLAY[status]}
    </span>
  );
}
