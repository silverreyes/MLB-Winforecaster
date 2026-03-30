import styles from './SpBadge.module.css';

interface SpBadgeProps {
  status: 'confirmed' | 'tbd' | 'may_have_changed';
  name?: string;
}

export function SpBadge({ status, name }: SpBadgeProps) {
  if (status === 'tbd') {
    return <span className={styles.tbd}>SP: TBD</span>;
  }

  return <span className={styles.confirmed}>{name ?? 'Unknown'}</span>;
}
