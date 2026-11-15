import test from "node:test";
import assert from "node:assert/strict";
import { weeklyStreaks, weekIndex, weekStart, shareableStreak, MILESTONES } from "../core/streaks.js";

// Local-time helpers so the tests hold in any time zone.
const at = (y, m, d, h = 12) => new Date(y, m - 1, d, h).getTime();
const sess = (t, extra = {}) => ({ id: String(t) + Math.random(), start: t, durationSec: 600, ...extra });
const NOW = at(2026, 11, 14);                    // a Saturday; its week began Monday 9 Nov 2026
const weeksAgo = (n, dow = 2) => at(2026, 11, 9 + dow - 7 * n);

test("weeks run Monday to Sunday", () => {
  assert.equal(new Date(weekStart(weekIndex(NOW))).getDay(), 1);
  assert.equal(weekIndex(at(2026, 11, 9, 0)), weekIndex(at(2026, 11, 15, 23)), "Monday 00:00 and Sunday 23:00 share a week");
  assert.notEqual(weekIndex(at(2026, 11, 15, 23)), weekIndex(at(2026, 11, 16, 0)), "the next Monday starts a new week");
  assert.equal(weekIndex(at(2026, 11, 8, 23)) + 1, weekIndex(at(2026, 11, 9, 0)), "Sunday night belongs to the week before");
});

test("one session a week is enough, more do not add weeks", () => {
  const s = weeklyStreaks([sess(weeksAgo(0)), sess(weeksAgo(0, 4)), sess(weeksAgo(1)), sess(weeksAgo(2))], NOW);
  assert.deepEqual([s.current, s.longest, s.totalActiveWeeks], [3, 3, 3]);
});

test("every category counts, including none and the earlier Partnered value; timed and manual alike", () => {
  const list = ["solo", "duo", "trio", "group", "partnered", null].map((c, i) => sess(weeksAgo(i), { category: c, segments: i % 2 ? [[1, 2]] : null }));
  assert.equal(weeklyStreaks(list, NOW).current, 6);
});

test("an unfinished current week never breaks a streak", () => {
  const s = weeklyStreaks([sess(weeksAgo(1)), sess(weeksAgo(2)), sess(weeksAgo(3))], NOW);
  assert.equal(s.current, 3);
  assert.equal(s.thisWeekActive, false);
  assert.equal(s.atRisk, true);
  assert.equal(weeklyStreaks([sess(weeksAgo(2)), sess(weeksAgo(3))], NOW).current, 0, "a fully missed week does break it");
});

test("longest streak, total weeks and run history", () => {
  const list = [0, 1, 4, 5, 6, 7, 10].map((n) => sess(weeksAgo(n)));
  const s = weeklyStreaks(list, NOW);
  assert.deepEqual([s.current, s.longest, s.totalActiveWeeks], [2, 4, 7]);
  assert.deepEqual(s.runs.map((r) => r.weeks), [1, 4, 2]);
});

test("recalculates after edits and deletions", () => {
  const list = [0, 1, 2, 3].map((n) => sess(weeksAgo(n)));
  assert.equal(weeklyStreaks(list, NOW).current, 4);
  assert.equal(weeklyStreaks(list.filter((_, i) => i !== 1), NOW).current, 1, "deleting last week's only session");
  const moved = list.map((s, i) => (i === 2 ? { ...s, start: weeksAgo(9) } : s));
  assert.deepEqual([weeklyStreaks(moved, NOW).current, weeklyStreaks(moved, NOW).longest], [2, 2], "moving a session to another week");
});

test("demo data, future entries and broken rows are excluded", () => {
  const s = weeklyStreaks([sess(weeksAgo(0), { demo: true }), sess(NOW + 864e5), { start: "x", durationSec: 5 }, { start: weeksAgo(1), durationSec: 0 }, null], NOW);
  assert.deepEqual([s.current, s.longest, s.totalActiveWeeks], [0, 0, 0]);
});

test("12-week view: oldest first, current week last, counts from real data", () => {
  const s = weeklyStreaks([sess(weeksAgo(0)), sess(weeksAgo(0, 5)), sess(weeksAgo(11)), sess(weeksAgo(12))], NOW);
  assert.equal(s.last12.length, 12);
  assert.equal(s.last12[11].current, true);
  assert.equal(s.last12[11].count, 2);
  assert.equal(s.last12[0].active, true);
  assert.equal(s.last12.filter((w) => w.active).length, 2, "the 13th week back is outside the view");
});

test("milestones at 4, 8, 12, 26 and 52 weeks", () => {
  assert.deepEqual(MILESTONES, [4, 8, 12, 26, 52]);
  const run = (n) => weeklyStreaks(Array.from({ length: n }, (_, i) => sess(weeksAgo(i))), NOW);
  assert.deepEqual(run(3).reached, []);
  assert.deepEqual([run(3).next, run(3).weeksToNext], [4, 1]);
  assert.deepEqual(run(12).reached, [4, 8, 12]);
  assert.deepEqual(run(53).reached, [4, 8, 12, 26, 52]);
  assert.equal(run(53).next, null);
  const old = weeklyStreaks(Array.from({ length: 8 }, (_, i) => sess(weeksAgo(i + 20))), NOW);
  assert.deepEqual([old.current, old.reached], [0, [4, 8]], "a milestone earned stays earned");
});

test("a 53-week run across daylight-saving changes and a year boundary stays unbroken", () => {
  const list = Array.from({ length: 53 }, (_, i) => sess(weeksAgo(i, i % 7)));
  assert.equal(weeklyStreaks(list, NOW).current, 53);
});

test("streak is only shareable when the person turns it on", () => {
  const s = weeklyStreaks([sess(weeksAgo(0))], NOW);
  assert.equal(shareableStreak(s, {}), null);
  assert.equal(shareableStreak(s, { showStreak: false }), null);
  assert.deepEqual(shareableStreak(s, { showStreak: true }), { weeks: 1 });
});
