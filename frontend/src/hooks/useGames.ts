import { useQuery } from '@tanstack/react-query';
import { fetchJson } from '../api/client';
import type { GamesDateResponse, GameResponse } from '../api/types';

function todayDateStr(): string {
  // Format as YYYY-MM-DD in local timezone
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function useGames(dateStr?: string) {
  const date = dateStr ?? todayDateStr();

  const query = useQuery({
    queryKey: ['games', date],
    queryFn: () => fetchJson<GamesDateResponse>(`/games/${date}`),
    staleTime: 55_000,
    refetchInterval: 60_000,
  });

  const games: GameResponse[] = query.data?.games ?? [];

  return {
    ...query,
    games,
    generatedAt: query.data?.generated_at ?? null,
  };
}
