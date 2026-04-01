import { useHistory } from '../hooks/useHistory';
import styles from './AccuracyStrip.module.css';

/** Hardcoded Brier scores from model_metadata.json (2015-2024 backtest) */
const ACCURACY_SCORES = [
  { label: 'LR SP:', value: '0.233' },
  { label: 'RF SP:', value: '0.234' },
  { label: 'XGB SP:', value: '0.235' },
  { label: 'LR Team:', value: '0.237' },
  { label: 'RF Team:', value: '0.238' },
  { label: 'XGB Team:', value: '0.240' },
];

function rollingDates(): { start: string; end: string } {
  const pad = (n: number) => String(n).padStart(2, '0');
  const fmt = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const end = new Date();
  end.setDate(end.getDate() - 1);
  const start = new Date(end);
  start.setDate(start.getDate() - 13); // 14-day window inclusive
  return { start: fmt(start), end: fmt(end) };
}

export function AccuracyStrip() {
  const { start, end } = rollingDates();
  const { pnl } = useHistory(start, end);

  const pnlDisplay = pnl !== null
    ? `${pnl.total >= 0 ? '+' : ''}${pnl.total.toFixed(1)}u (${pnl.wins}-${pnl.losses})`
    : '\u2014';

  return (
    <div className={styles.strip}>
      <div className={styles.inner}>
        <span className={styles.heading}>
          Model Accuracy (Brier Score, lower is better)
        </span>
        <div className={styles.row}>
          <div className={styles.scores}>
            {ACCURACY_SCORES.map((score, i) => (
              <span key={score.label} className={styles.scoreItem}>
                {i > 0 && <span className={styles.divider}>|</span>}
                <span className={styles.label}>{score.label}</span>
                <span className={styles.value}>{score.value}</span>
              </span>
            ))}
            <span className={styles.scoreItem}>
              <span className={styles.divider}>|</span>
              <span className={styles.label}>14d P&amp;L:</span>
              <span className={styles.value}>{pnlDisplay}</span>
            </span>
          </div>
          <a href="#/history" className={styles.historyLink}>
            View History &rarr;
          </a>
        </div>
      </div>
    </div>
  );
}
