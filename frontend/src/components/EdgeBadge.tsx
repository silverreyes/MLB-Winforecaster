import { Tooltip } from './Tooltip';
import styles from './EdgeBadge.module.css';

interface EdgeBadgeProps {
  signal: 'BUY_YES' | 'BUY_NO';
  magnitude: number;
}

const TOOLTIP_YES = 'Pays $1 if the home team wins. You pay the displayed price.';
const TOOLTIP_NO = 'Pays $1 if the home team loses. You pay 1 minus the Yes price.';

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
