// Weekly activity streaks. A week runs Monday 00:00 to Sunday 23:59 in the device's local time.
// One saved session of any category, timed or logged by hand, makes a week active. Demo rows never count.
// Everything is recomputed from the session list, so edits and deletions are always reflected.

export const MILESTONES = [4, 8, 12, 26, 52];

// Monday of the local week containing t, as a day number (days since 1970-01-01, local calendar).
// Working in calendar days rather than milliseconds keeps daylight-saving changes from shifting a week.
export function weekIndex(t) {
  const d = new Date(t);
  const dayNum = Math.round(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 864e5);
  const dow = (d.getDay() + 6) % 7;                    // Monday = 0
  return (dayNum - dow - 4) / 7;                       // 1970-01-05 was a Monday => week 0
}
export function weekStart(idx) {
  const u = new Date((idx * 7 + 4) * 864e5);
  return new Date(u.getUTCFullYear(), u.getUTCMonth(), u.getUTCDate()).getTime();
}

export function weeklyStreaks(sessions, now = Date.now()) {
  const counts = new Map();
  for (const s of sessions) {
    if (!s || s.demo || typeof s.start !== "number" || !(s.durationSec > 0) || s.start > now) continue;
    const w = weekIndex(s.start);
    counts.set(w, (counts.get(w) || 0) + 1);
  }
  const thisWeek = weekIndex(now), weeks = [...counts.keys()].sort((a, b) => a - b);

  // Current streak: the week in progress extends a streak if it is active, and never breaks one if it is not yet.
  let current = 0, w = counts.has(thisWeek) ? thisWeek : thisWeek - 1;
  while (counts.has(w)) { current++; w--; }

  let longest = 0, run = 0, prev = null, longestEnd = null;
  for (const k of weeks) {
    run = prev !== null && k === prev + 1 ? run + 1 : 1;
    if (run > longest) { longest = run; longestEnd = k; }
    prev = k;
  }

  const last12 = [];
  for (let k = thisWeek - 11; k <= thisWeek; k++) last12.push({ start: weekStart(k), count: counts.get(k) || 0, active: counts.has(k), current: k === thisWeek });

  // History of every run, for Insights.
  const runs = [];
  for (const k of weeks) {
    const r = runs[runs.length - 1];
    if (r && k === r.endWeek + 1) { r.endWeek = k; r.length++; } else runs.push({ startWeek: k, endWeek: k, length: 1 });
  }

  const reached = MILESTONES.filter((m) => longest >= m);
  const next = MILESTONES.find((m) => current < m) || null;
  return {
    current, longest, totalActiveWeeks: weeks.length,
    thisWeekActive: counts.has(thisWeek),
    atRisk: current > 0 && !counts.has(thisWeek),      // informational only; the UI must not nag
    last12, reached, next, weeksToNext: next ? next - current : 0,
    longestEnded: longestEnd === null ? null : weekStart(longestEnd),
    runs: runs.map((r) => ({ start: weekStart(r.startWeek), weeks: r.length })),
  };
}

// What may be put on a shared card. Off unless the person turns streak visibility on.
export function shareableStreak(streak, settings) {
  if (!settings || settings.showStreak !== true) return null;
  return { weeks: streak.current };
}
