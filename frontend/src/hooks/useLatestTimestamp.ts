import { useQuery } from '@tanstack/react-query';
import { fetchJson } from '../api/client';
import type { LatestTimestampResponse } from '../api/types';

export function useLatestTimestamp() {
  return useQuery({
    queryKey: ['latest-timestamp'],
    queryFn: () => fetchJson<LatestTimestampResponse>('/predictions/latest-timestamp'),
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
    staleTime: 55_000,
  });
}
