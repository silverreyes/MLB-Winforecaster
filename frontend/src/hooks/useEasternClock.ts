import { useState, useEffect } from 'react';

interface EasternClockState {
  dateStr: string;   // e.g., "Monday, March 30" (ET date — baseball context)
  timeStr: string;   // e.g., "2:34 PM" (browser local time, no ET label)
  nextUpdate: string; // e.g., "Next update: 1:00 PM" or "Next update: 10:00 AM tomorrow"
}

const PIPELINE_RUN_HOURS_ET = [10, 13, 17]; // 10 AM, 1 PM, 5 PM ET

// ET date formatter — kept in ET for baseball-day context
const dateFmt = new Intl.DateTimeFormat('en-US', {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
  timeZone: 'America/New_York',
});

// Browser-local time formatter — no timeZone specified, uses browser locale
const localTimeFmt = new Intl.DateTimeFormat('en-US', {
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
});

// ET hour extractor — used internally to determine which run is next
const etHourFmt = new Intl.DateTimeFormat('en-US', {
  hour: 'numeric',
  minute: '2-digit',
  hour12: false,
  timeZone: 'America/New_York',
});

/**
 * Convert a pipeline run hour (in ET) to a display string in the user's browser timezone.
 *
 * Strategy: compute the current offset between local hour and ET hour, then
 * apply that offset to the target run hour to get the local equivalent.
 */
function etRunHourToLocalDisplay(now: Date, etRunHour: number, tomorrow: boolean): string {
  // Get current ET hour (24h)
  const etParts = etHourFmt.formatToParts(now);
  let currentEtHour = 0;
  for (const part of etParts) {
    if (part.type === 'hour') currentEtHour = Number(part.value);
  }

  // Local hour (24h)
  const currentLocalHour = now.getHours();
  const hourOffset = currentLocalHour - currentEtHour;

  // Build a Date representing "today (or tomorrow) at etRunHour:00 local-equivalent"
  const runDate = new Date(now);
  if (tomorrow) runDate.setDate(runDate.getDate() + 1);
  runDate.setHours(etRunHour + hourOffset, 0, 0, 0);

  return localTimeFmt.format(runDate);
}

function computeNextUpdate(now: Date): string {
  // Determine current ET time to pick which run is next
  const etParts = etHourFmt.formatToParts(now);
  let currentEtHour = 0;
  let currentEtMinute = 0;
  for (const part of etParts) {
    if (part.type === 'hour') currentEtHour = Number(part.value);
    if (part.type === 'minute') currentEtMinute = Number(part.value);
  }
  const currentEtTotal = currentEtHour * 60 + currentEtMinute;

  for (const runHour of PIPELINE_RUN_HOURS_ET) {
    if (runHour * 60 > currentEtTotal) {
      return 'Next update: ' + etRunHourToLocalDisplay(now, runHour, false);
    }
  }

  // Past all runs today — next is 10 AM ET tomorrow
  return 'Next update: ' + etRunHourToLocalDisplay(now, 10, true) + ' tomorrow';
}

function computeClock(): EasternClockState {
  const now = new Date();
  const dateStr = dateFmt.format(now);
  const timeStr = localTimeFmt.format(now);
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
