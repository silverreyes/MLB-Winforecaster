import styles from './FutureDateBanner.module.css';

interface FutureDateBannerProps {
  viewMode: 'tomorrow' | 'future';
}

const BANNER_COPY: Record<'tomorrow' | 'future', { heading: string; body: string }> = {
  tomorrow: {
    heading: "Tomorrow's Matchups",
    body: 'Games with both starting pitchers confirmed are marked PRELIMINARY. Predictions will be generated on game day.',
  },
  future: {
    heading: 'Upcoming Schedule',
    body: 'Predictions available on game day.',
  },
};

export function FutureDateBanner({ viewMode }: FutureDateBannerProps) {
  const copy = BANNER_COPY[viewMode];
  return (
    <div className={styles.container}>
      <h2 className={styles.heading}>{copy.heading}</h2>
      <p className={styles.body}>{copy.body}</p>
    </div>
  );
}
