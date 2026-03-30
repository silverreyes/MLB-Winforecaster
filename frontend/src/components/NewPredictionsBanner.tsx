import styles from './NewPredictionsBanner.module.css';

interface NewPredictionsBannerProps {
  visible: boolean;
  onRefresh: () => void;
}

export function NewPredictionsBanner({ visible, onRefresh }: NewPredictionsBannerProps) {
  if (!visible) return null;

  return (
    <div className={styles.banner}>
      <span className={styles.message}>New predictions available</span>
      <button className={styles.button} onClick={onRefresh}>
        Load latest predictions
      </button>
    </div>
  );
}
