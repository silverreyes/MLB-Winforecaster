import { todayDateStr } from '../hooks/useGames';
import type { ViewMode } from '../api/types';
import styles from './DateNavigator.module.css';

interface DateNavigatorProps {
  selectedDate: string;        // YYYY-MM-DD
  onDateChange: (date: string) => void;
  viewMode: ViewMode | null;
}

function formatDate(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function DateNavigator({ selectedDate, onDateChange, viewMode }: DateNavigatorProps) {
  const today = todayDateStr();
  const isToday = selectedDate === today;

  // Show stale note when server says "historical" but client thinks it's today
  const showStaleNote = viewMode === 'historical' && isToday;

  const goToPreviousDay = () => {
    const d = new Date(selectedDate + 'T12:00:00');
    d.setDate(d.getDate() - 1);
    onDateChange(formatDate(d));
  };

  const goToNextDay = () => {
    const d = new Date(selectedDate + 'T12:00:00');
    d.setDate(d.getDate() + 1);
    onDateChange(formatDate(d));
  };

  const goToToday = () => {
    onDateChange(todayDateStr());
  };

  return (
    <div className={styles.navigator}>
      <div className={styles.inner}>
        <button onClick={goToPreviousDay} className={styles.arrow} aria-label="Previous day">
          {'\u2190'}
        </button>
        <input
          type="date"
          value={selectedDate}
          onChange={(e) => onDateChange(e.target.value)}
          className={styles.datePicker}
        />
        <button
          onClick={goToToday}
          className={`${styles.todayBtn} ${isToday ? styles.todayBtnDisabled : ''}`}
          aria-label="Go to today"
          disabled={isToday}
        >
          Today
        </button>
        {showStaleNote && (
          <span className={styles.staleNote}>A new day has started. Click Today to refresh.</span>
        )}
        <button onClick={goToNextDay} className={styles.arrow} aria-label="Next day">
          {'\u2192'}
        </button>
      </div>
    </div>
  );
}
