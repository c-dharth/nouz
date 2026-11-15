// VOUZ session timer: a small state machine over persisted timestamps.
// Elapsed time is always derived from stored wall-clock segments, never from a ticking counter,
// so backgrounding, screen lock and process death cannot lose or invent time.
// Every function is pure: it takes a state and `now` (ms) and returns a new state.
//
// Persisted shape (compatible with the existing `active` object in vouz.v1):
//   { id, state: "running"|"paused", segments: [[startMs, endMs|null], ...], category, lastSeen }

export const MAX_SESSION_MS = 24 * 3600 * 1000;      // matches the 24 h limit on manual entries
export const STALE_AFTER_MS = 6 * 3600 * 1000;       // no heartbeat for this long => ask the user

const newId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
const last = (a) => a[a.length - 1];
const clone = (s) => ({ ...s, segments: s.segments.map((x) => [x[0], x[1]]) });

export function stateOf(s) {
  if (!s || !Array.isArray(s.segments) || !s.segments.length) return "idle";
  return last(s.segments)[1] === null ? "running" : "paused";
}

export function start(prev, now, opts = {}) {
  if (stateOf(prev) !== "idle") return prev;                       // one session at a time
  return { id: opts.id || newId(), state: "running", segments: [[now, null]], category: opts.category ?? null, lastSeen: now };
}

export function pause(s, now) {
  if (stateOf(s) !== "running") return s;
  const n = clone(s), seg = last(n.segments);
  seg[1] = Math.max(seg[0], now);                                  // a clock set backwards cannot make negative time
  n.state = "paused"; n.lastSeen = now;
  return n;
}

export function resume(s, now) {
  if (stateOf(s) !== "paused") return s;
  const n = clone(s);
  n.segments.push([Math.max(now, last(n.segments)[1]), null]);
  n.state = "running"; n.lastSeen = now;
  return n;
}

export function setCategory(s, category) {
  return stateOf(s) === "idle" ? s : { ...clone(s), category: category ?? null };
}

// Call on a slow interval and on every visibility change. Only moves lastSeen forward.
export function heartbeat(s, now) {
  if (stateOf(s) === "idle" || now <= (s.lastSeen || 0)) return s;
  return { ...clone(s), lastSeen: now };
}

export function elapsedMs(s, now) {
  if (stateOf(s) === "idle") return 0;
  let t = 0;
  for (const [a, b] of s.segments) t += Math.max(0, (b === null ? now : b) - a);
  return Math.min(t, MAX_SESSION_MS);
}

// Run on launch and on return to foreground.
// A running session keeps running across lock and background: that is the point of timestamps.
// But if the app was gone for a long time, we do not guess. We report it and let the person choose.
export function recover(s, now) {
  const st = stateOf(s);
  if (st === "idle") return { state: null, status: "none" };
  if (!validSegments(s.segments)) return { state: null, status: "corrupt" };
  const seen = s.lastSeen || last(s.segments)[0];
  if (st === "running") {
    if (now < last(s.segments)[0]) return { state: s, status: "clock-moved-back", suggestedEnd: seen };
    if (now - seen > STALE_AFTER_MS || elapsedMs(s, now) >= MAX_SESSION_MS) return { state: s, status: "stale", suggestedEnd: seen };
  }
  return { state: s, status: "ok" };
}

// Resolve a stale session: "trim" ends it where the app was last seen, "keep" trusts the clock.
export function resolveStale(s, choice, now) {
  if (choice === "discard") return null;
  if (choice === "trim") {
    const n = clone(s), seg = last(n.segments);
    if (seg[1] === null) seg[1] = Math.max(seg[0], Math.min(s.lastSeen || seg[0], now));
    n.state = "paused";
    return n;
  }
  return heartbeat(s, now);
}

// Stop: produce a draft for the save form. The draft keeps the timer's id, so saving twice cannot create two sessions.
export function finish(s, now) {
  if (stateOf(s) === "idle") return null;
  const n = stateOf(s) === "running" ? pause(s, now) : clone(s);
  const segments = n.segments.filter(([a, b]) => b > a);
  if (!segments.length) segments.push([n.segments[0][0], n.segments[0][0] + 1000]);
  const durationSec = Math.max(1, Math.round(Math.min(MAX_SESSION_MS, segments.reduce((t, [a, b]) => t + (b - a), 0)) / 1000));
  return { id: n.id, fromTimer: true, start: segments[0][0], durationSec, segments, category: n.category ?? null };
}

export function validSegments(segs) {
  if (!Array.isArray(segs) || !segs.length) return false;
  let prev = -Infinity;
  for (let i = 0; i < segs.length; i++) {
    const x = segs[i];
    if (!Array.isArray(x) || typeof x[0] !== "number" || !isFinite(x[0]) || x[0] < prev) return false;
    if (x[1] === null) { if (i !== segs.length - 1) return false; prev = x[0]; continue; }
    if (typeof x[1] !== "number" || !isFinite(x[1]) || x[1] < x[0]) return false;
    prev = x[1];
  }
  return true;
}

// ---- session list operations (create, edit, delete, duplicate guard) ----

// Idempotent by id: committing the same draft again updates, never duplicates.
export function commit(sessions, rec, now) {
  const i = sessions.findIndex((x) => x.id === rec.id);
  if (i >= 0) { const out = sessions.slice(); out[i] = { ...out[i], ...rec, updatedAt: now }; return out; }
  return sessions.concat([{ reflection: "", ...rec, createdAt: now, updatedAt: now }]);
}

export function remove(sessions, deleted, id, now) {
  return { sessions: sessions.filter((x) => x.id !== id), deleted: { ...deleted, [id]: now } };
}

// A likely accidental double entry: another session starting within a minute with the same length (±5 s).
export function findDuplicate(sessions, rec) {
  return sessions.find((x) => x.id !== rec.id && !x.demo && Math.abs(x.start - rec.start) <= 60000 && Math.abs(x.durationSec - rec.durationSec) <= 5) || null;
}

// Sessions that overlap in time with this one (shown as a warning, never blocked).
export function overlaps(sessions, rec) {
  const a0 = rec.start, a1 = rec.start + rec.durationSec * 1000;
  return sessions.filter((x) => x.id !== rec.id && !x.demo && x.start < a1 && x.start + x.durationSec * 1000 > a0);
}
