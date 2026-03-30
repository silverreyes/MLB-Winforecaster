import type { GameGroup } from '../api/types';
import { GameCard } from './GameCard';
import styles from './GameCardGrid.module.css';

interface GameCardGridProps {
  games: GameGroup[];
  isStale: boolean;
}

export function GameCardGrid({ games, isStale }: GameCardGridProps) {
  return (
    <div className={`${styles.grid} ${isStale ? styles.stale : ''}`}>
      {games.map((game) => (
        <GameCard
          key={`${game.away_team}-${game.home_team}`}
          game={game}
          isStale={isStale}
        />
      ))}
    </div>
  );
}
