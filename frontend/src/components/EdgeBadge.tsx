import styles from './EdgeBadge.module.css';

interface EdgeBadgeProps {
  signal: 'BUY_YES' | 'BUY_NO';
  magnitude: number;
}

export function EdgeBadge({ signal, magnitude }: EdgeBadgeProps) {
  const isBuyYes = signal === 'BUY_YES';
  const text = isBuyYes
    ? `BUY YES +${magnitude.toFixed(1)}pts`
    : `BUY NO -${Math.abs(magnitude).toFixed(1)}pts`;

  return (
    <span className={`${styles.badge} ${isBuyYes ? styles.buyYes : styles.buyNo}`}>
      {text}
    </span>
  );
}
