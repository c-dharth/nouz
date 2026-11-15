import test from "node:test";
import assert from "node:assert/strict";
import { enqueue, mergeSessions, drain } from "../core/sync.js";

const s = (id, updatedAt, extra = {}) => ({ id, start: 1, durationSec: 60, updatedAt, ...extra });

test("queue coalesces repeated changes to one record", () => {
  let q = [];
  q = enqueue(q, { kind: "upsert", id: "a", at: 1 }); q = enqueue(q, { kind: "upsert", id: "a", at: 2 }); q = enqueue(q, { kind: "upsert", id: "b", at: 3 });
  q = enqueue(q, { kind: "delete", id: "a", at: 4 }); q = enqueue(q, { kind: "settings", at: 5 }); q = enqueue(q, { kind: "settings", at: 6 });
  assert.deepEqual(q.map((o) => o.kind + (o.id || "")), ["upsertb", "deletea", "settings"]);
});

test("conflict: the newer edit wins on either side", () => {
  const r = mergeSessions([s("a", 5, { notes: "local" }), s("b", 1)], [s("a", 3, { notes: "remote" }), s("b", 9, { notes: "remote b" }), s("c", 2)]);
  const by = Object.fromEntries(r.sessions.map((x) => [x.id, x]));
  assert.deepEqual([by.a.notes, by.b.notes, !!by.c], ["local", "remote b", true]);
  assert.deepEqual(r.conflicts, [{ id: "a", kept: "local" }, { id: "b", kept: "remote" }]);
});

test("conflict: a deletion wins unless the session was edited after it", () => {
  assert.equal(mergeSessions([s("a", 5)], [], {}, { a: 9 }).sessions.length, 0, "deleted on another device");
  assert.equal(mergeSessions([], [s("a", 5)], { a: 9 }, {}).sessions.length, 0, "deleted here, still on the server");
  assert.equal(mergeSessions([s("a", 12)], [], {}, { a: 9 }).sessions.length, 1, "edited after the deletion: kept");
  assert.deepEqual(mergeSessions([], [], { a: 3 }, { a: 8, b: 1 }).deleted, { a: 8, b: 1 });
});

test("merge is the same whichever device runs it", () => {
  const A = [s("a", 5), s("b", 2)], B = [s("a", 3), s("c", 7)], dA = { c: 1 }, dB = { b: 4 };
  const ids = (r) => r.sessions.map((x) => x.id + x.updatedAt).sort();
  assert.deepEqual(ids(mergeSessions(A, B, dA, dB)), ids(mergeSessions(B, A, dB, dA)));
});

test("offline: nothing is lost, order is kept, retries back off", async () => {
  const q = [{ kind: "upsert", id: "a", tries: 0 }, { kind: "upsert", id: "b", tries: 0 }];
  const r = await drain(q, async () => { throw { retryable: true }; }, 1000);
  assert.deepEqual([r.sent, r.offline, r.queue.length], [0, true, 2]);
  assert.deepEqual([r.queue[0].tries, r.queue[0].notBefore, r.queue[1].tries], [1, 3000, 0]);
  const again = await drain(r.queue, async () => {}, 2000);
  assert.equal(again.sent, 0, "waits until the back-off has passed");
  const later = await drain(r.queue, async () => {}, 4000);
  assert.deepEqual([later.sent, later.queue.length, later.offline], [2, 0, false]);
});

test("a change the server refuses for good is reported and does not block the rest", async () => {
  const q = [{ kind: "upsert", id: "bad", tries: 0 }, { kind: "upsert", id: "ok", tries: 0 }], sent = [];
  const r = await drain(q, async (op) => { if (op.id === "bad") throw { retryable: false, message: "denied" }; sent.push(op.id); });
  assert.deepEqual([sent, r.queue.length, r.rejected[0].reason], [["ok"], 0, "denied"]);
});
