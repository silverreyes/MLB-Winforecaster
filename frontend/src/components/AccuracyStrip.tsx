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

function formatPnL(total: number, wins: number, losses: number): string {
  return `${total >= 0 ? '+' : ''}${total.toFixed(1)}u (${wins}-${losses})`;
}

interface AccuracyStripProps {
  viewedDate: string;
}

export function AccuracyStrip({ viewedDate }: AccuracyStripProps) {
  const { start, end } = rollingDates();
  const { pnl: rollingPnl } = useHistory(start, end);

  // Daily P&L: only fetch for historical dates (before today)
  const isHistorical = viewedDate < new Date().toISOString().slice(0, 10);
  const { pnl: dailyPnl } = useHistory(
    isHistorical ? viewedDate : '',
    isHistorical ? viewedDate : '',
  );

  const rollingDisplay = rollingPnl !== null
    ? formatPnL(rollingPnl.total, rollingPnl.wins, rollingPnl.losses)
    : '\u2014';

  // Only show daily P&L if historical and there were buy signals that day
  const showDaily = isHistorical && dailyPnl !== null && (dailyPnl.wins + dailyPnl.losses) > 0;
  const dailyDisplay = showDaily
    ? formatPnL(dailyPnl!.total, dailyPnl!.wins, dailyPnl!.losses)
    : null;

  const [, month, day] = viewedDate.split('-');
  const dailyLabel = `${parseInt(month)}/${parseInt(day)} P&L:`;

  return (
    <div className={styles.strip}>
      <div className={styles.inner}>
        <div className={styles.pnlRow}>
          <div className={styles.pnlGroup}>
            <span className={styles.pnlLabel}>14d P&amp;L:</span>
            <span className={styles.pnlValue}>{rollingDisplay}</span>
          </div>
          {showDaily && (
            <>
              <span className={styles.pnlDivider}>|</span>
              <div className={styles.pnlGroup}>
                <span className={styles.pnlLabel}>{dailyLabel}</span>
                <span className={styles.pnlValue}>{dailyDisplay}</span>
              </div>
            </>
          )}
        </div>
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
          </div>
          <a href="#/history" className={styles.historyLink}>
            View History &rarr;
          </a>
        </div>
      </div>
    </div>
  );
}
