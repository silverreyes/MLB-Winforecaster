import { usePredictions } from './hooks/usePredictions';
import { useLatestTimestamp } from './hooks/useLatestTimestamp';
import { Header } from './components/Header';
import { AccuracyStrip } from './components/AccuracyStrip';
import { GameCardGrid } from './components/GameCardGrid';
import { SkeletonCard } from './components/SkeletonCard';
import { EmptyState } from './components/EmptyState';

const STALE_THRESHOLD_MS = 3 * 60 * 60 * 1000; // 3 hours
const SKELETON_COUNT = 6;

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
      <Header
        lastUpdated={latestPredictionAt}
        isStale={isStale}
        isOffline={isError}
      />
      <AccuracyStrip />

      {/* New predictions banner placeholder */}
      {hasNewPredictions && (
        <div style={{
          background: 'rgba(217, 119, 6, 0.15)',
          color: '#D97706',
          padding: '8px 16px',
          textAlign: 'center',
          fontFamily: 'var(--font-ui)',
          fontSize: '14px',
        }}>
          New predictions available
        </div>
      )}

      {/* Loading: skeleton cards */}
      {isLoading && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
          gap: '32px',
          maxWidth: '1200px',
          margin: '0 auto',
          padding: '48px 24px 24px',
        }}>
          {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Error state placeholder */}
      {isError && !isLoading && (
        <div style={{
          maxWidth: '480px',
          margin: '48px auto',
          padding: '24px',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: '8px',
          textAlign: 'center',
        }}>
          <h2 style={{
            fontFamily: 'var(--font-ui)',
            fontSize: '20px',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            margin: '0 0 8px',
          }}>
            Dashboard offline
          </h2>
          <p style={{
            fontFamily: 'var(--font-ui)',
            fontSize: '16px',
            fontWeight: 400,
            color: 'var(--color-text-secondary)',
            margin: 0,
          }}>
            Unable to reach the predictions API. The pipeline may be updating — try again in a few minutes.
          </p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && games.length === 0 && <EmptyState />}

      {/* Game card grid */}
      {!isLoading && !isError && games.length > 0 && (
        <GameCardGrid games={games} isStale={isStale} />
      )}
    </div>
  );
}

export default App;
