import test from "node:test";
import assert from "node:assert/strict";
import { configFrom, backend, syncOnce } from "../core/backend.js";
import { enqueue } from "../core/sync.js";

test("no credentials means local-only, not an error", () => {
  assert.equal(configFrom({}), null);
  assert.deepEqual(configFrom({ VITE_SUPABASE_URL: "https://x.supabase.co/", VITE_SUPABASE_ANON_KEY: "anon" }), { url: "https://x.supabase.co", key: "anon" });
});

test("refuses an insecure URL and anything that looks like the service role key", () => {
  assert.throws(() => configFrom({ SUPABASE_URL: "http://x", SUPABASE_ANON_KEY: "k" }));
  assert.throws(() => configFrom({ SUPABASE_URL: "https://x", SUPABASE_ANON_KEY: "abc.service_role.def" }));
  assert.throws(() => configFrom({ SUPABASE_URL: "https://x", SUPABASE_ANON_KEY: "same", SUPABASE_SERVICE_ROLE_KEY: "same" }));
});

// A pretend server: stores sessions per id, applies the same newer-wins rule as upsert_session.
function fakeServer() {
  const rows = new Map(), notes = new Map(), log = [];
  let down = false;
  const fetchImpl = async (url, init) => {
    if (down) throw new Error("network");
    log.push({ url, body: init.body });
    const ok = (b) => ({ ok: true, status: 200, json: async () => b });
    if (url.endsWith("/rpc/upsert_session")) { const s = JSON.parse(init.body).s, cur = rows.get(s.id); if (!cur || cur.client_updated_at < s.updatedAt) rows.set(s.id, { id: s.id, started_at: new Date(s.start).toISOString(), duration_sec: s.durationSec, segments: s.segments, category: s.category, participants: s.participants, satisfaction: s.satisfaction, shared_note: s.sharedNote, title: s.title, tags: s.tags, mood: s.mood, hr_avg: null, hr_peak: null, client_updated_at: s.updatedAt, deleted_at: s.deletedAt ? new Date(s.deletedAt).toISOString() : null }); return ok(true); }
    if (url.includes("/session_notes?on_conflict")) { const n = JSON.parse(init.body); notes.set(n.session_id, n); return ok([]); }
    if (url.includes("/sessions?select")) return ok([...rows.values()]);
    if (url.includes("/session_notes?select")) return ok([...notes.values()]);
    return { ok: false, status: 404, json: async () => ({}) };
  };
  return { fetchImpl, rows, notes, log, set down(v) { down = v; } };
}
const cfg = { url: "https://x.supabase.co", key: "anon" };
const sess = (id, updatedAt, extra = {}) => ({ id, start: 1763150000000, durationSec: 600, segments: null, category: "couple", participants: 2, tags: [], mood: "", notes: "", reflection: "", hrAvg: "", hrPeak: "", updatedAt, ...extra });

test("offline: changes stay queued and local data is untouched", async () => {
  const srv = fakeServer(); srv.down = true;
  const data = { sessions: [sess("a", 5, { notes: "private" })], deleted: {}, settings: {} };
  const r = await syncOnce(data, enqueue([], { kind: "upsert", id: "a", at: 5, userId: "u" }), backend(cfg, async () => "tok", srv.fetchImpl), 1000);
  assert.deepEqual([r.status, r.queue.length, r.data.sessions.length], ["offline", 1, 1]);
});

test("signed out: nothing is sent", async () => {
  const srv = fakeServer();
  const r = await syncOnce({ sessions: [sess("a", 5)], deleted: {}, settings: {} }, enqueue([], { kind: "upsert", id: "a", at: 5, userId: "u" }), backend(cfg, async () => null, srv.fetchImpl), 1000);
  assert.deepEqual([r.status, srv.log.length], ["offline", 0]);
});

test("back online: queue drains, notes go to their own table, other devices' sessions arrive", async () => {
  const srv = fakeServer();
  srv.rows.set("remote", { id: "remote", started_at: new Date(1763000000000).toISOString(), duration_sec: 300, segments: null, category: "poly", participants: 3, shared_note: "", title: "", tags: [], mood: "", hr_avg: 110, hr_peak: null, client_updated_at: 3, deleted_at: null });
  const data = { sessions: [sess("a", 5, { notes: "PRIVATE NOTE" }), sess("d", 1, { demo: true })], deleted: {}, settings: {} };
  const r = await syncOnce(data, enqueue([], { kind: "upsert", id: "a", at: 5, userId: "u" }), backend(cfg, async () => "tok", srv.fetchImpl), 1000);
  assert.deepEqual([r.status, r.queue.length], ["ok", 0]);
  assert.deepEqual(r.data.sessions.map((s) => s.id).sort(), ["a", "d", "remote"]);
  assert.equal(r.data.sessions.find((s) => s.id === "remote").hrAvg, "110");
  assert.deepEqual([r.data.sessions.find((s) => s.id === "remote").category, r.data.sessions.find((s) => s.id === "remote").participants], ["poly", 3]);
  assert.equal(r.data.sessions.find((s) => s.id === "a").notes, "PRIVATE NOTE");
  const upsert = srv.log.find((l) => l.url.endsWith("/rpc/upsert_session"));
  assert.ok(!upsert.body.includes("PRIVATE NOTE"), "the session row never carries notes");
  assert.ok(!srv.rows.has("d"), "demo sessions are never uploaded");
});

test("conflict: a newer edit from another device wins, an older one does not", async () => {
  const srv = fakeServer(), api = backend(cfg, async () => "tok", srv.fetchImpl);
  await api.push({ kind: "upsert", id: "a", userId: "u" }, { sessions: [sess("a", 9, { title: "newer elsewhere" })] });
  const r = await syncOnce({ sessions: [sess("a", 5, { title: "older here" })], deleted: {}, settings: {} }, enqueue([], { kind: "upsert", id: "a", at: 5, userId: "u" }), api, 1000);
  assert.equal(r.data.sessions[0].title, "newer elsewhere");
  assert.deepEqual(r.conflicts, [{ id: "a", kept: "remote" }]);
});

test("a deletion made offline reaches the server and removes the session on other devices", async () => {
  const srv = fakeServer(), api = backend(cfg, async () => "tok", srv.fetchImpl);
  await api.push({ kind: "upsert", id: "a", userId: "u" }, { sessions: [sess("a", 5)] });
  const r = await syncOnce({ sessions: [], deleted: { a: 8 }, settings: {} }, enqueue([], { kind: "delete", id: "a", at: 8, userId: "u" }), api, 1000);
  assert.ok(srv.rows.get("a").deleted_at);
  const other = await syncOnce({ sessions: [sess("a", 5)], deleted: {}, settings: {} }, [], api, 2000);
  assert.equal(other.data.sessions.length, 0);
});
