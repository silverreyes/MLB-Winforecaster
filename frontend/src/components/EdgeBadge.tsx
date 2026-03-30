import { Tooltip } from './Tooltip';
import styles from './EdgeBadge.module.css';

interface EdgeBadgeProps {
  signal: 'BUY_YES' | 'BUY_NO';
  magnitude: number;
}

const TOOLTIP_YES = 'Kalshi contract: pays $1 if home wins';
const TOOLTIP_NO = 'Kalshi contract: pays $1 if home loses';

export function EdgeBadge({ signal, magnitude }: EdgeBadgeProps) {
  const isBuyYes = signal === 'BUY_YES';
  const text = isBuyYes
    ? `BUY YES +${magnitude.toFixed(1)}pts`
    : `BUY NO -${Math.abs(magnitude).toFixed(1)}pts`;
  const tooltipText = isBuyYes ? TOOLTIP_YES : TOOLTIP_NO;

  return (
    <span className={`${styles.badge} ${isBuyYes ? styles.buyYes : styles.buyNo}`}>
      {text}
      <Tooltip text={tooltipText} />
    </span>
  );
}
