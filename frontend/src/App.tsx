import { useState, useEffect } from 'react';
import { usePredictions } from './hooks/usePredictions';
import { useLatestTimestamp } from './hooks/useLatestTimestamp';
import { Header } from './components/Header';
import { AccuracyStrip } from './components/AccuracyStrip';
import { AboutModels } from './components/AboutModels';
import { NewPredictionsBanner } from './components/NewPredictionsBanner';
import { GameCardGrid } from './components/GameCardGrid';
import { SkeletonCard } from './components/SkeletonCard';
import { EmptyState } from './components/EmptyState';
import { ErrorState } from './components/ErrorState';
import styles from './App.module.css';

const STALE_THRESHOLD_MS = 3 * 60 * 60 * 1000; // 3 hours
const SKELETON_COUNT = 6;

function App() {
  const { data, isLoading, isError, games, refetch } = usePredictions();
  const { data: timestampData } = useLatestTimestamp();

  // Track displayed data timestamp for comparison
  const displayedTimestamp = data?.latest_prediction_at ?? null;

  // DASH-05: Staleness check (3-hour threshold)
  const isStale = displayedTimestamp
    ? Date.now() - new Date(displayedTimestamp).getTime() > STALE_THRESHOLD_MS
    : false;

  // DASH-06: New predictions detection
  const hasNewPredictions = !!(
    timestampData?.timestamp &&
    displayedTimestamp &&
    new Date(timestampData.timestamp).getTime() > new Date(displayedTimestamp).getTime()
  );

  // DASH-07: Error state
  const isOffline = isError;

  // Track last successful timestamp for error state display
  const [lastSuccessTimestamp, setLastSuccessTimestamp] = useState<string | null>(null);
  useEffect(() => {
    if (displayedTimestamp) {
      setLastSuccessTimestamp(displayedTimestamp);
    }
  }, [displayedTimestamp]);

  // Handler for "Load latest predictions" banner button
  const handleRefresh = () => {
    refetch();
  };

  return (
    <div>
      <Header
        lastUpdated={displayedTimestamp}
        isStale={isStale}
        isOffline={isOffline}
      />
      <AccuracyStrip />
      <AboutModels />
      <NewPredictionsBanner
        visible={hasNewPredictions}
        onRefresh={handleRefresh}
      />
      <main>
        {isLoading && !data ? (
          <div className={styles.skeletonGrid}>
            {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : isError && !data ? (
          <ErrorState lastSuccessfulTimestamp={lastSuccessTimestamp} />
        ) : games.length === 0 ? (
          <EmptyState />
        ) : (
          <GameCardGrid
            games={games}
            isStale={isStale || isOffline}
          />
        )}
      </main>
    </div>
  );
}

export default App;
