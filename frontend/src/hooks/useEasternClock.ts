import { useState, useEffect } from 'react';

interface EasternClockState {
  dateStr: string;   // e.g., "Monday, March 30"
  timeStr: string;   // e.g., "2:34 PM ET"
  nextUpdate: string; // e.g., "Next update: 1:00 PM ET" or "Next update: 10:00 AM ET tomorrow"
}

const PIPELINE_RUN_HOURS = [10, 13, 17]; // 10 AM, 1 PM, 5 PM ET

const RUN_LABELS: Record<number, string> = {
  10: '10:00 AM',
  13: '1:00 PM',
  17: '5:00 PM',
};

const dateFmt = new Intl.DateTimeFormat('en-US', {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
  timeZone: 'America/New_York',
});

const timeFmt = new Intl.DateTimeFormat('en-US', {
  hour: 'numeric',
  minute: '2-digit',
  timeZone: 'America/New_York',
});

const etPartsFmt = new Intl.DateTimeFormat('en-US', {
  hour: 'numeric',
  minute: '2-digit',
  hour12: false,
  timeZone: 'America/New_York',
});

function computeNextUpdate(now: Date): string {
  const parts = etPartsFmt.formatToParts(now);
  let currentHour = 0;
  let currentMinute = 0;
  for (const part of parts) {
    if (part.type === 'hour') currentHour = Number(part.value);
    if (part.type === 'minute') currentMinute = Number(part.value);
  }

  const currentTotalMinutes = currentHour * 60 + currentMinute;

  for (const runHour of PIPELINE_RUN_HOURS) {
    const runTotalMinutes = runHour * 60;
    if (runTotalMinutes > currentTotalMinutes) {
      return 'Next update: ' + RUN_LABELS[runHour] + ' ET';
    }
  }

  // No future run today (current time >= 17:00 ET)
  return 'Next update: 10:00 AM ET tomorrow';
}

function computeClock(): EasternClockState {
  const now = new Date();

  const dateStr = dateFmt.format(now);
  const timeStr = timeFmt.format(now) + ' ET';
  const nextUpdate = computeNextUpdate(now);

  return { dateStr, timeStr, nextUpdate };
}

export function useEasternClock(): EasternClockState {
  const [clock, setClock] = useState<EasternClockState>(computeClock);

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | undefined;

    const msUntilNextSecond = 1000 - (Date.now() % 1000);

    const timeoutId = setTimeout(() => {
      setClock(computeClock());

      intervalId = setInterval(() => {
        setClock(computeClock());
      }, 1000);
    }, msUntilNextSecond);

    return () => {
      clearTimeout(timeoutId);
      if (intervalId !== undefined) {
        clearInterval(intervalId);
      }
    };
  }, []);

  return clock;
}
