import type { GameResponse, ViewMode } from '../api/types';
import { GameCard } from './GameCard';
import styles from './GameCardGrid.module.css';

interface GameCardGridProps {
  games: GameResponse[];
  isStale: boolean;
  viewMode: ViewMode | null;
}

export function GameCardGrid({ games, isStale, viewMode }: GameCardGridProps) {
  return (
    <div className={`${styles.grid} ${isStale ? styles.stale : ''}`}>
      {games.map((game) => (
        <GameCard
          key={game.game_id}
          game={game}
          viewMode={viewMode}
        />
      ))}
    </div>
  );
}
