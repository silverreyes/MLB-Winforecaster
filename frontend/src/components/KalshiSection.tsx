import { EdgeBadge } from './EdgeBadge';
import styles from './KalshiSection.module.css';

interface KalshiSectionProps {
  price: number | null;
  edgeSignal: string | null;
  edgeMagnitude: number | null;
}

export function KalshiSection({ price, edgeSignal, edgeMagnitude }: KalshiSectionProps) {
  const formattedPrice = price !== null ? `${Math.round(price * 100)}c` : '--';
  const showEdge =
    (edgeSignal === 'BUY_YES' || edgeSignal === 'BUY_NO') &&
    edgeMagnitude !== null;

  return (
    <div className={styles.section}>
      <span className={styles.sectionLabel}>KALSHI</span>
      <div className={styles.row}>
        <span className={styles.price}>{formattedPrice}</span>
        {showEdge && (
          <EdgeBadge
            signal={edgeSignal as 'BUY_YES' | 'BUY_NO'}
            magnitude={edgeMagnitude!}
          />
        )}
      </div>
    </div>
  );
}
