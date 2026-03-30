import styles from './EmptyState.module.css';

export function EmptyState() {
  return (
    <div className={styles.container}>
      <h2 className={styles.heading}>No games scheduled today</h2>
      <p className={styles.body}>
        Check back on the next game day. The pipeline runs daily at 10am and 1pm ET.
      </p>
    </div>
  );
}
