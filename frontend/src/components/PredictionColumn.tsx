import type { PredictionResponse } from '../api/types';
import styles from './PredictionColumn.module.css';

interface PredictionColumnProps {
  prediction: PredictionResponse;
  isPrimary: boolean;
  label: string;
}

function formatProb(value: number | null): string {
  if (value === null) return '--';
  return `${(value * 100).toFixed(1)}%`;
}

export function PredictionColumn({ prediction, isPrimary, label }: PredictionColumnProps) {
  const { ensemble_prob, lr_prob, rf_prob, xgb_prob } = prediction;

  return (
    <div className={styles.column}>
      <span className={styles.label}>{label}</span>
      <span className={`${styles.heroNumber} ${!isPrimary ? styles.muted : ''}`}>
        {formatProb(ensemble_prob)}
      </span>
      <div className={styles.modelRows}>
        <div className={styles.modelRow}>
          <span className={styles.modelLabel}>LR</span>
          <span className={styles.modelValue}>{formatProb(lr_prob)}</span>
        </div>
        <div className={styles.modelRow}>
          <span className={styles.modelLabel}>RF</span>
          <span className={styles.modelValue}>{formatProb(rf_prob)}</span>
        </div>
        <div className={styles.modelRow}>
          <span className={styles.modelLabel}>XGB</span>
          <span className={styles.modelValue}>{formatProb(xgb_prob)}</span>
        </div>
      </div>
    </div>
  );
}
