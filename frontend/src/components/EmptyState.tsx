import type { ViewMode } from '../api/types';
import styles from './EmptyState.module.css';

interface EmptyStateProps {
  viewMode: ViewMode | null;
  selectedDate: string;
}

function formatDisplayDate(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00');
  return new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(d);
}

function getCopy(viewMode: ViewMode | null, selectedDate: string): { heading: string; body: string } {
  switch (viewMode) {
    case 'historical':
      return {
        heading: `No games on ${formatDisplayDate(selectedDate)}`,
        body: 'There were no MLB games scheduled for this date.',
      };
    case 'tomorrow':
      return {
        heading: 'No games scheduled for tomorrow',
        body: 'Check back closer to game time for the schedule.',
      };
    case 'future':
      return {
        heading: `No games scheduled for ${formatDisplayDate(selectedDate)}`,
        body: 'The MLB schedule for this date is not yet available.',
      };
    case 'live':
    default:
      return {
        heading: 'No games scheduled today',
        body: 'Check back on the next game day. The pipeline runs daily at 10 AM and 1 PM ET.',
      };
  }
}

export function EmptyState({ viewMode, selectedDate }: EmptyStateProps) {
  const copy = getCopy(viewMode, selectedDate);
  return (
    <div className={styles.container}>
      <h2 className={styles.heading}>{copy.heading}</h2>
      <p className={styles.body}>{copy.body}</p>
    </div>
  );
}
