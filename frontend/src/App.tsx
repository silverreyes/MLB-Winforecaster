import { useState, useEffect, useRef } from 'react';
import { useGames, todayDateStr } from './hooks/useGames';
import { useLatestTimestamp } from './hooks/useLatestTimestamp';
import { Header } from './components/Header';
import { DateNavigator } from './components/DateNavigator';
import { AccuracyStrip } from './components/AccuracyStrip';
import { AboutModels } from './components/AboutModels';
import { NewPredictionsBanner } from './components/NewPredictionsBanner';
import { FutureDateBanner } from './components/FutureDateBanner';
import { GameCardGrid } from './components/GameCardGrid';
import { SkeletonCard } from './components/SkeletonCard';
import { EmptyState } from './components/EmptyState';
import { ErrorState } from './components/ErrorState';
import { HistoryPage } from './components/HistoryPage';
import styles from './App.module.css';

const STALE_THRESHOLD_MS = 3 * 60 * 60 * 1000; // 3 hours
const SKELETON_COUNT = 6;

function App() {
  const [selectedDate, setSelectedDate] = useState<string>(todayDateStr());
  const { data, isLoading, isError, games, refetch, viewMode } = useGames(selectedDate);
  const { data: timestampData } = useLatestTimestamp();

  // Pipeline run timestamp (from /predictions/latest-timestamp)
  const pipelineTimestamp = timestampData?.timestamp ?? null;

  // Track the pipeline timestamp that was current when this page loaded
  const initialTimestampRef = useRef<string | null>(null);
  useEffect(() => {
    if (timestampData?.timestamp && !initialTimestampRef.current) {
      initialTimestampRef.current = timestampData.timestamp;
    }
  }, [timestampData?.timestamp]);

  // DASH-05: Staleness check against pipeline run time (3-hour threshold)
  const isStale = pipelineTimestamp
    ? Date.now() - new Date(pipelineTimestamp).getTime() > STALE_THRESHOLD_MS
    : false;

  // DASH-06: New predictions detection — fires when pipeline runs after page load
  const hasNewPredictions = !!(
    timestampData?.timestamp &&
    initialTimestampRef.current &&
    new Date(timestampData.timestamp).getTime() > new Date(initialTimestampRef.current).getTime()
  );

  // DASH-07: Error state
  const isOffline = isError;

  // Track last successful pipeline timestamp for error state display
  const [lastSuccessTimestamp, setLastSuccessTimestamp] = useState<string | null>(null);
  useEffect(() => {
    if (pipelineTimestamp) {
      setLastSuccessTimestamp(pipelineTimestamp);
    }
  }, [pipelineTimestamp]);

  // Handler for "Load latest predictions" banner button
  const handleRefresh = () => {
    refetch();
  };

  // Hash-based routing
  const [currentHash, setCurrentHash] = useState(window.location.hash || '#/');

  useEffect(() => {
    const onHashChange = () => setCurrentHash(window.location.hash || '#/');
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const isHistoryPage = currentHash === '#/history';

  return (
    <div>
      <Header
        lastUpdated={pipelineTimestamp}
        isStale={isStale}
        isOffline={isOffline}
      />
      {isHistoryPage ? (
        <HistoryPage />
      ) : (
        <>
          <DateNavigator
            selectedDate={selectedDate}
            onDateChange={setSelectedDate}
            viewMode={viewMode}
          />
          <AccuracyStrip viewedDate={selectedDate} />
          <AboutModels />
          <NewPredictionsBanner
            visible={hasNewPredictions}
            onRefresh={handleRefresh}
          />
          {(viewMode === 'tomorrow' || viewMode === 'future') && games.length > 0 && (
            <FutureDateBanner viewMode={viewMode} />
          )}
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
              <EmptyState viewMode={viewMode ?? null} selectedDate={selectedDate} />
            ) : (
              <GameCardGrid
                games={games}
                isStale={isStale || isOffline}
                viewMode={viewMode}
              />
            )}
          </main>
        </>
      )}
    </div>
  );
}

export default App;
