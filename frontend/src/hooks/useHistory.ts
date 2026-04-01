import { useQuery } from '@tanstack/react-query';
import { fetchJson } from '../api/client';
import type { HistoryResponse } from '../api/types';

export function useHistory(startDate: string, endDate: string) {
  const query = useQuery({
    queryKey: ['history', startDate, endDate],
    queryFn: () => fetchJson<HistoryResponse>(`/history?start=${startDate}&end=${endDate}`),
    staleTime: 5 * 60 * 1000,  // 5 minutes -- history data changes infrequently
  });

  return {
    ...query,
    games: query.data?.games ?? [],
    accuracy: query.data?.accuracy ?? {},
    pnl: query.data?.pnl ?? null,
  };
}
