import styles from './ErrorState.module.css';

interface ErrorStateProps {
  lastSuccessfulTimestamp: string | null;
}

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(date);
}

export function ErrorState({ lastSuccessfulTimestamp }: ErrorStateProps) {
  return (
    <div className={styles.container}>
      <h2 className={styles.heading}>Dashboard offline</h2>
      <p className={styles.body}>
        Unable to reach the predictions API.
        {lastSuccessfulTimestamp
          ? ` Showing data from ${formatTimestamp(lastSuccessfulTimestamp)}. The pipeline may be updating -- try again in a few minutes.`
          : ' The pipeline may be updating -- try again in a few minutes.'}
      </p>
    </div>
  );
}
