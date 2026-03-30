import { usePredictions } from './hooks/usePredictions';
import { useLatestTimestamp } from './hooks/useLatestTimestamp';

const STALE_THRESHOLD_MS = 3 * 60 * 60 * 1000; // 3 hours

function App() {
  const { data, isLoading, isError, games } = usePredictions();
  const { data: timestampData } = useLatestTimestamp();

  const latestPredictionAt = data?.latest_prediction_at ?? null;

  const isStale = latestPredictionAt
    ? Date.now() - new Date(latestPredictionAt).getTime() > STALE_THRESHOLD_MS
    : false;

  const hasNewPredictions = !!(
    timestampData?.timestamp &&
    latestPredictionAt &&
    new Date(timestampData.timestamp).getTime() > new Date(latestPredictionAt).getTime()
  );

  return (
    <div>
      {/* Header placeholder */}
      <header>
        <h1>MLB Win Forecaster</h1>
        <p>Last updated: {latestPredictionAt ?? 'loading...'}</p>
        {isStale && <p>Data may be stale</p>}
      </header>

      {/* New predictions banner placeholder */}
      {hasNewPredictions && <p>New predictions available</p>}

      {/* Main content */}
      {isLoading && <p>Loading...</p>}
      {isError && <p>Error loading predictions</p>}
      {!isLoading && !isError && games.length === 0 && <p>No games scheduled today</p>}
      {!isLoading && !isError && games.length > 0 && (
        <p>{games.length} games loaded</p>
      )}
    </div>
  );
}

export default App;
