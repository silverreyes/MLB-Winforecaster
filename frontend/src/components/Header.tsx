import { useEasternClock } from '../hooks/useEasternClock';
import styles from './Header.module.css';

interface HeaderProps {
  lastUpdated: string | null;
  isStale: boolean;
  isOffline: boolean;
}

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(date);
}

export function Header({ lastUpdated, isStale, isOffline }: HeaderProps) {
  const formattedTime = lastUpdated ? formatTimestamp(lastUpdated) : null;
  const { dateStr, timeStr, nextUpdate } = useEasternClock();

  return (
    <header className={styles.header}>
      <div className={styles.topRow}>
        <div className={styles.left}>
          <h1 className={styles.title}>MLB Win Forecaster</h1>
          <p className={styles.subtitle}>
            Model-ensemble win probabilities vs. Kalshi market prices
          </p>
        </div>
        <div className={styles.right}>
          {isOffline && <span className={styles.offlineBadge}>Dashboard offline</span>}
          {isStale && formattedTime ? (
            <span className={styles.staleTimestamp}>
              Data may be stale — last updated {formattedTime}
            </span>
          ) : formattedTime ? (
            <span className={styles.timestamp}>Last updated {formattedTime}</span>
          ) : null}
        </div>
      </div>
      <div className={styles.clockRow}>
        <span className={styles.dateText}>{dateStr}</span>
        <span className={styles.separator}>|</span>
        <span className={styles.clockText}>{timeStr}</span>
        <span className={styles.separator}>|</span>
        <span className={styles.nextUpdate}>{nextUpdate}</span>
      </div>
    </header>
  );
}
