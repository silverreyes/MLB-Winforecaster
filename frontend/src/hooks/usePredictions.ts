import { useQuery } from '@tanstack/react-query';
import { fetchJson } from '../api/client';
import type { TodayResponse, GameGroup, PredictionResponse } from '../api/types';

function groupPredictions(predictions: PredictionResponse[]): GameGroup[] {
  const map = new Map<string, GameGroup>();

  for (const pred of predictions) {
    const key = `${pred.home_team}-${pred.away_team}`;
    let group = map.get(key);
    if (!group) {
      group = {
        home_team: pred.home_team,
        away_team: pred.away_team,
        game_date: pred.game_date,
        pre_lineup: null,
        post_lineup: null,
      };
      map.set(key, group);
    }
    if (pred.prediction_version === 'post_lineup' || pred.prediction_version === 'confirmation') {
      group.post_lineup = pred;
    } else if (pred.prediction_version === 'pre_lineup') {
      group.pre_lineup = pred;
    }
  }

  return Array.from(map.values());
}

export function usePredictions() {
  const query = useQuery({
    queryKey: ['predictions-today'],
    queryFn: () => fetchJson<TodayResponse>('/predictions/today'),
    staleTime: 55_000,
  });

  const games = query.data ? groupPredictions(query.data.predictions) : [];

  return {
    ...query,
    games,
  };
}
