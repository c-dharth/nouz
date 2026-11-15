import test from "node:test";
import assert from "node:assert/strict";
import * as T from "../core/timer.js";

const H = 3600e3, t0 = Date.UTC(2026, 10, 14, 20, 0, 0);

test("start, pause, resume, stop: only active time counts", () => {
  let s = T.start(null, t0);
  assert.equal(T.stateOf(s), "running");
  s = T.pause(s, t0 + 10 * 60e3);
  assert.equal(T.elapsedMs(s, t0 + 50 * 60e3), 10 * 60e3, "paused time is not counted");
  s = T.resume(s, t0 + 30 * 60e3);
  const d = T.finish(s, t0 + 35 * 60e3);
  assert.equal(d.durationSec, 15 * 60);
  assert.equal(d.segments.length, 2);
  assert.equal(d.start, t0);
});

test("invalid transitions are ignored, not errors", () => {
  const s = T.start(null, t0);
  assert.equal(T.start(s, t0 + 5), s, "second start does nothing");
  assert.equal(T.resume(s, t0 + 5), s, "resume while running does nothing");
  const p = T.pause(s, t0 + 1000);
  assert.equal(T.pause(p, t0 + 2000), p, "pause while paused does nothing");
  assert.equal(T.finish(null, t0), null);
});

test("accuracy does not depend on ticks: 3 h in the background with no timer callbacks", () => {
  const s = T.start(null, t0);
  assert.equal(T.elapsedMs(s, t0 + 3 * H), 3 * H);
});

test("survives a full persist / kill / relaunch cycle", () => {
  let s = T.start(null, t0, { category: "duo" });
  s = T.pause(s, t0 + 60e3); s = T.resume(s, t0 + 120e3);
  const revived = JSON.parse(JSON.stringify(s));           // what comes back from storage after the process dies
  const r = T.recover(revived, t0 + 20 * 60e3);
  assert.equal(r.status, "ok");
  assert.equal(T.elapsedMs(r.state, t0 + 20 * 60e3), 60e3 + 18 * 60e3);
  assert.equal(r.state.category, "duo");
});

test("screen lock while paused stays paused and adds nothing", () => {
  const s = JSON.parse(JSON.stringify(T.pause(T.start(null, t0), t0 + 5 * 60e3)));
  const r = T.recover(s, t0 + 10 * H);
  assert.equal(r.status, "ok");
  assert.equal(T.elapsedMs(r.state, t0 + 10 * H), 5 * 60e3);
});

test("a running session abandoned for hours is flagged, never silently saved", () => {
  let s = T.start(null, t0); s = T.heartbeat(s, t0 + 20 * 60e3);
  const r = T.recover(JSON.parse(JSON.stringify(s)), t0 + 9 * H);
  assert.equal(r.status, "stale");
  assert.equal(r.suggestedEnd, t0 + 20 * 60e3);
  const trimmed = T.resolveStale(r.state, "trim", t0 + 9 * H);
  assert.equal(T.finish(trimmed, t0 + 9 * H).durationSec, 20 * 60, "trim ends it where the app was last alive");
  assert.equal(T.finish(T.resolveStale(r.state, "keep", t0 + 9 * H), t0 + 9 * H).durationSec, 9 * 3600);
  assert.equal(T.resolveStale(r.state, "discard", t0 + 9 * H), null);
});

test("clock set backwards cannot create negative or inflated time", () => {
  const s = T.start(null, t0);
  assert.equal(T.recover(s, t0 - H).status, "clock-moved-back");
  const p = T.pause(s, t0 - H);
  assert.equal(T.elapsedMs(p, t0), 0);
  assert.ok(T.validSegments(p.segments));
  assert.equal(T.finish(p, t0).durationSec, 1, "a zero-length session still saves as 1 s, never 0 or negative");
});

test("duration is capped at 24 h", () => {
  const s = T.start(null, t0);
  assert.equal(T.elapsedMs(s, t0 + 40 * H), T.MAX_SESSION_MS);
  assert.equal(T.finish(s, t0 + 40 * H).durationSec, 86400);
});

test("corrupt persisted timer state is detected", () => {
  assert.equal(T.recover({ segments: [[t0, null], [t0 + 5, null]] }, t0 + 10).status, "corrupt");
  assert.equal(T.recover({ segments: [[t0 + 10, t0]] }, t0 + 20).status, "corrupt");
  assert.equal(T.recover({ segments: [["x", null]] }, t0).status, "corrupt");
  assert.equal(T.recover(null, t0).status, "none");
  assert.equal(T.recover({ segments: [] }, t0).status, "none");
});

test("heartbeat only moves forward", () => {
  const s = T.heartbeat(T.start(null, t0), t0 + 5000);
  assert.equal(T.heartbeat(s, t0 + 1000), s);
  assert.equal(T.heartbeat(s, t0 + 9000).lastSeen, t0 + 9000);
});

test("category can be set before or during, and reaches the draft", () => {
  let s = T.start(null, t0, { category: "solo" });
  s = T.setCategory(s, "trio");
  assert.equal(T.finish(s, t0 + 60e3).category, "trio");
  assert.equal(T.finish(T.start(null, t0), t0 + 60e3).category, null, "category stays optional");
});

test("session CRUD: saving the same draft twice does not duplicate", () => {
  const d = T.finish(T.start(null, t0), t0 + 600e3);
  let list = T.commit([], { ...d, title: "" }, t0 + 601e3);
  list = T.commit(list, { ...d, title: "again" }, t0 + 602e3);
  assert.equal(list.length, 1);
  assert.equal(list[0].title, "again");
  assert.equal(list[0].createdAt, t0 + 601e3, "created time is kept on edit");
  assert.equal(list[0].updatedAt, t0 + 602e3);
});

test("session CRUD: edit keeps private fields, delete leaves a tombstone", () => {
  let list = T.commit([], { id: "a", start: t0, durationSec: 600, notes: "mine", category: "partnered" }, 1);
  list = T.commit(list, { id: "a", durationSec: 900 }, 2);
  assert.deepEqual([list[0].notes, list[0].durationSec, list[0].category], ["mine", 900, "partnered"]);
  const r = T.remove(list, {}, "a", 3);
  assert.equal(r.sessions.length, 0);
  assert.equal(r.deleted.a, 3);
});

test("duplicate and overlap detection for manual entries", () => {
  const list = [{ id: "a", start: t0, durationSec: 1200 }, { id: "demo", start: t0, durationSec: 1200, demo: true }];
  assert.equal(T.findDuplicate(list, { id: "b", start: t0 + 30e3, durationSec: 1203 }).id, "a");
  assert.equal(T.findDuplicate(list, { id: "b", start: t0 + 5 * 60e3, durationSec: 1200 }), null);
  assert.equal(T.findDuplicate(list, { id: "a", start: t0, durationSec: 1200 }), null, "a session is not its own duplicate");
  assert.deepEqual(T.overlaps(list, { id: "b", start: t0 + 10 * 60e3, durationSec: 60 }).map((x) => x.id), ["a"]);
  assert.equal(T.overlaps(list, { id: "b", start: t0 + 30 * 60e3, durationSec: 60 }).length, 0);
});
