import { useState } from 'react';
import { useHistory } from '../hooks/useHistory';
import styles from './HistoryPage.module.css';

function formatDate(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function defaultStart(): string {
  const d = new Date();
  d.setDate(d.getDate() - 14);
  return formatDate(d);
}

function defaultEnd(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return formatDate(d);
}

function formatProb(prob: number | null): string {
  if (prob === null) return '\u2014';
  return `${(prob * 100).toFixed(1)}%`;
}

function formatDisplayDate(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00');
  return new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric',
  }).format(d);
}

export function HistoryPage() {
  const [startDate, setStartDate] = useState(defaultStart);
  const [endDate, setEndDate] = useState(defaultEnd);
  const { games, accuracy, isLoading, isError } = useHistory(startDate, endDate);

  const handleStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setStartDate(e.target.value);
  };
  const handleEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Clamp to today at most (history = completed games)
    const today = formatDate(new Date());
    const val = e.target.value;
    setEndDate(val > today ? today : val);
  };

  return (
    <div className={styles.container}>
      {/* Page header */}
      <div className={styles.pageHeader}>
        <h2 className={styles.pageTitle}>Prediction History</h2>
        <a href="#/" className={styles.backLink}>
          &larr; Back to Today
        </a>
      </div>

      {/* Accuracy summary */}
      <div className={styles.accuracyStrip}>
        {['lr', 'rf', 'xgb'].map((model, i) => {
          const acc = accuracy[model];
          const label = model.toUpperCase();
          const pct = acc ? `${acc.pct}%` : '\u2014';
          const detail = acc ? `(${acc.correct}/${acc.total})` : '';
          return (
            <span key={model} className={styles.accuracyItem}>
              {i > 0 && <span className={styles.divider}>|</span>}
              <span className={styles.accuracyLabel}>{label}:</span>
              <span className={styles.accuracyValue}>{pct}</span>
              <span className={styles.accuracyDetail}>{detail}</span>
            </span>
          );
        })}
      </div>

      {/* Date range picker */}
      <div className={styles.dateRow}>
        <label className={styles.dateLabel}>
          Start
          <input
            type="date"
            value={startDate}
            onChange={handleStartChange}
            className={styles.dateInput}
            max={endDate}
          />
        </label>
        <label className={styles.dateLabel}>
          End
          <input
            type="date"
            value={endDate}
            onChange={handleEndChange}
            className={styles.dateInput}
            max={formatDate(new Date())}
          />
        </label>
      </div>

      {/* Table or empty state */}
      {isLoading ? (
        <p className={styles.loading}>Loading history...</p>
      ) : isError ? (
        <p className={styles.error}>Failed to load history data.</p>
      ) : games.length === 0 ? (
        <div className={styles.empty}>
          <h3 className={styles.emptyHeading}>No completed games in this range</h3>
          <p className={styles.emptyBody}>
            Try selecting a different date range with completed games.
          </p>
        </div>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>Date</th>
                <th className={styles.th}>Matchup</th>
                <th className={styles.th}>Score</th>
                <th className={styles.thNum}>LR%</th>
                <th className={styles.thNum}>RF%</th>
                <th className={styles.thNum}>XGB%</th>
                <th className={styles.thCenter}></th>
              </tr>
            </thead>
            <tbody>
              {games.map((g, i) => {
                const score = g.home_score !== null && g.away_score !== null
                  ? `${g.away_score}\u2013${g.home_score}`
                  : '\u2014';
                return (
                  <tr key={`${g.game_date}-${g.home_team}-${g.away_team}-${i}`} className={styles.row}>
                    <td className={styles.td}>{formatDisplayDate(g.game_date)}</td>
                    <td className={styles.td}>{g.away_team} @ {g.home_team}</td>
                    <td className={styles.td}>{score}</td>
                    <td className={styles.tdNum}>{formatProb(g.lr_prob)}</td>
                    <td className={styles.tdNum}>{formatProb(g.rf_prob)}</td>
                    <td className={styles.tdNum}>{formatProb(g.xgb_prob)}</td>
                    <td className={styles.tdCenter}>
                      {g.prediction_correct ? (
                        <span className={styles.correct}>&#10003;</span>
                      ) : (
                        <span className={styles.incorrect}>&#10005;</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
