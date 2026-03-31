import type { GameResponse } from '../api/types';
import { GameCard } from './GameCard';
import styles from './GameCardGrid.module.css';

interface GameCardGridProps {
  games: GameResponse[];
  isStale: boolean;
}

export function GameCardGrid({ games, isStale }: GameCardGridProps) {
  return (
    <div className={`${styles.grid} ${isStale ? styles.stale : ''}`}>
      {games.map((game) => (
        <GameCard
          key={game.game_id}
          game={game}
          isStale={isStale}
        />
      ))}
    </div>
  );
}
