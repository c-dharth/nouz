import test from "node:test";
import assert from "node:assert/strict";
import { Vault, KEY, SCHEMA, memoryAdapter, sealed, keyFromSecureStore, migrate, fresh } from "../core/storage.js";

// Data exactly as earlier builds wrote it.
const legacy = () => ({ v: 1, onboarded: true, stamp: 5, user: { name: "Sid", mode: "local", createdAt: 1 },
  settings: { social: false, privateProfile: true, defaultVis: "connections", regular: { n: 2, w: 4 }, pinHash: "h", pinSalt: "s" },
  sessions: [
    { id: "old1", title: "A", start: 1000, durationSec: 900, segments: null, category: "solo", tags: [], mood: "", notes: "keepme", hrAvg: "", hrPeak: "", createdAt: 1, updatedAt: 1 },
    { id: "old2", title: "B", start: 2000, durationSec: 1800, segments: [[2000, 3800000]], category: "partnered", tags: ["x"], mood: "Tender", notes: "", hrAvg: "120", hrPeak: "", createdAt: 1, updatedAt: 1 },
  ], deleted: { gone: 7 }, active: { segments: [[5000, null]] }, draft: null, blocks: [], ignored: [] });

test("legacy vouz.v1 data loads under the same key with nothing lost", async () => {
  const a = memoryAdapter({ [KEY]: JSON.stringify(legacy()) });
  const { data, report } = await new Vault(a).load();
  assert.equal(report.migratedFrom, 1);
  assert.equal(data.schema, SCHEMA);
  assert.equal(data.v, 1, "sync format marker is untouched");
  assert.equal(data.sessions.length, 2);
  assert.equal(data.sessions[0].notes, "keepme");
  assert.equal(data.sessions[1].category, "partnered", "Partnered is never rewritten as Duo");
  assert.deepEqual(data.sessions[1].segments, [[2000, 3800000]]);
  assert.deepEqual(data.settings.regular, { n: 2, w: 4 }, "custom-frequency goal kept");
  assert.equal(data.settings.showStreak, false, "new settings default to private");
  assert.equal(data.deleted.gone, 7);
  assert.deepEqual(data.active, { segments: [[5000, null]], category: null }, "a running timer survives the upgrade");
  assert.deepEqual(JSON.parse(await a.get(KEY + ".pre" + SCHEMA)), legacy(), "an untouched pre-migration copy is kept");
});

test("migration is idempotent and refuses data from a newer build", () => {
  const once = migrate(legacy()).data, twice = migrate(JSON.parse(JSON.stringify(once)));
  assert.equal(twice.migrated, false);
  assert.deepEqual(twice.data, once);
  assert.throws(() => migrate({ v: 1, schema: SCHEMA + 1, sessions: [] }), { code: "newer" });
});

test("migration drops only rows that could never have displayed", () => {
  const d = legacy(); d.sessions.push(null, { id: "bad", start: "x", durationSec: 5 }, { id: "g", start: 3000, durationSec: 60, category: "group", groupSize: "6" }, { id: "odd", start: 4000, durationSec: 60, category: "quartet" });
  const out = migrate(d).data.sessions;
  assert.deepEqual(out.map((s) => s.id), ["old1", "old2", "g", "odd"]);
  assert.equal(out[2].groupSize, 6);
  assert.equal(out[3].category, null);
});

test("first run gives a fresh, private-by-default vault", async () => {
  const { data, report } = await new Vault(memoryAdapter()).load();
  assert.equal(report.source, null);
  assert.deepEqual([data.sessions.length, data.settings.social, data.onboarded], [0, false, false]);
});

test("save keeps the previous good copy as a backup", async () => {
  const a = memoryAdapter(), v = new Vault(a), d = fresh();
  await v.save(d); d.sessions.push({ id: "n", start: 1, durationSec: 60 }); await v.save(d);
  assert.equal(JSON.parse(await a.get(KEY)).sessions.length, 1);
  assert.equal(JSON.parse(await a.get(KEY + ".bak")).sessions.length, 0);
  assert.equal(await a.get(KEY + ".next"), null);
});

test("corrupted main copy: recovers from backup and quarantines the damaged bytes", async () => {
  const good = migrate(legacy()).data;
  const a = memoryAdapter({ [KEY]: '{"v":1,"sessions":[{"id":"ol', [KEY + ".bak"]: JSON.stringify(good) });
  const { data, report } = await new Vault(a).load();
  assert.equal(report.recovered, true);
  assert.equal(report.source, KEY + ".bak");
  assert.equal(data.sessions.length, 2);
  assert.equal(await a.get(report.quarantined), '{"v":1,"sessions":[{"id":"ol', "damaged data is kept, not deleted");
  assert.equal(JSON.parse(await a.get(KEY)).sessions.length, 2, "main copy is repaired");
});

test("crash between writing and committing: the newest complete copy wins", async () => {
  const older = migrate(legacy()).data, newer = JSON.parse(JSON.stringify(older)); newer.sessions.push({ id: "n", start: 9, durationSec: 60, tags: [], people: [], category: null, groupSize: null });
  const a = memoryAdapter({ [KEY]: JSON.stringify(older), [KEY + ".next"]: JSON.stringify(newer) });
  assert.equal((await new Vault(a).load()).data.sessions.length, 3);
  const b = memoryAdapter({ [KEY]: JSON.stringify(older), [KEY + ".next"]: JSON.stringify(newer).slice(0, 40) });
  assert.equal((await new Vault(b).load()).data.sessions.length, 2, "a half-written pending copy is ignored");
});

test("everything unreadable: starts fresh without throwing, and keeps the evidence", async () => {
  const a = memoryAdapter({ [KEY]: "not json", [KEY + ".bak"]: "[]" });
  const { data, report } = await new Vault(a).load();
  assert.equal(data.sessions.length, 0);
  assert.ok(report.quarantined);
});

test("refuses to write something that would not load again", async () => {
  const a = memoryAdapter({ [KEY]: JSON.stringify(fresh()) });
  await assert.rejects(new Vault(a).save({ v: 1, sessions: "oops" }));
  assert.ok(Array.isArray(JSON.parse(await a.get(KEY)).sessions), "the good copy is untouched");
});

test("concurrent updates are serialised: no lost writes", async () => {
  const v = new Vault(memoryAdapter()); await v.save(fresh());
  await Promise.all(Array.from({ length: 25 }, (_, i) => v.update((d) => { d.sessions.push({ id: "s" + i, start: i + 1, durationSec: 60 }); })));
  assert.equal((await v.load()).data.sessions.length, 25);
});

test("works with no network at all (offline persistence round trip)", async () => {
  const a = memoryAdapter(); let v = new Vault(a);
  await v.update((d) => { d.active = { id: "t", segments: [[100, null]], category: "duo", lastSeen: 100 }; });
  v = new Vault(a);                                               // simulate a cold start
  assert.equal((await v.load()).data.active.category, "duo");
});

test("export leaves out demo rows and the screen-lock hash; import adds without overwriting", async () => {
  const d = migrate(legacy()).data; d.sessions.push({ id: "demo1", start: 5, durationSec: 60, demo: true });
  const file = Vault.exportOf(d);
  assert.equal(file.sessions.length, 2);
  assert.ok(!("pinHash" in file.settings) && !("pinSalt" in file.settings) && !JSON.stringify(file).includes("demo1"));
  const target = fresh(); target.sessions.push({ id: "old1", start: 1000, durationSec: 900, notes: "local edit", updatedAt: 99 }); target.deleted.old2 = 1;
  const r = Vault.importInto(target, JSON.parse(JSON.stringify(file)));
  assert.deepEqual([r.added, r.skipped], [1, 1]);
  assert.equal(target.sessions.find((s) => s.id === "old1").notes, "local edit", "existing sessions are not overwritten");
  assert.equal(target.deleted.old2, undefined, "an imported session is not immediately re-deleted");
  assert.throws(() => Vault.importInto(fresh(), { hello: 1 }), { code: "format" });
});

test("wipe removes every copy, including backups and quarantined data", async () => {
  const a = memoryAdapter({ [KEY]: "broken", [KEY + ".bak"]: JSON.stringify(fresh()), other: "untouched" });
  const v = new Vault(a); await v.load(); await v.save(fresh()); await v.wipe();
  assert.deepEqual(await a.keys(), ["other"]);
});

test("sealed adapter: stored bytes are ciphertext, wrong key cannot read, tampering is detected", async () => {
  const raw = memoryAdapter(), key = crypto.getRandomValues(new Uint8Array(32)), v = new Vault(sealed(raw, async () => key));
  const d = fresh(); d.sessions.push({ id: "s", start: 1, durationSec: 60, notes: "VERYPRIVATE" }); await v.save(d);
  const stored = await raw.get(KEY);
  assert.ok(!stored.includes("VERYPRIVATE") && stored.startsWith('{"enc":1,'));
  assert.equal((await new Vault(sealed(raw, async () => key)).load()).data.sessions[0].notes, "VERYPRIVATE");
  const other = sealed(raw, async () => crypto.getRandomValues(new Uint8Array(32)));
  await assert.rejects(other.get(KEY));
  const o = JSON.parse(stored); o.ct = o.ct.slice(0, -4) + (o.ct.slice(-4) === "AAAA" ? "BBBB" : "AAAA"); await raw.set(KEY, JSON.stringify(o));
  await assert.rejects(sealed(raw, async () => key).get(KEY), "modified ciphertext fails authentication");
  await raw.set(KEY + ".bak", stored);
  await assert.rejects(sealed(raw, async () => key).get(KEY + ".bak"), "a sealed value cannot be replayed under another name");
});

test("turning sealing on later: existing readable data loads and is sealed on the next save", async () => {
  const raw = memoryAdapter({ [KEY]: JSON.stringify(legacy()) }), key = crypto.getRandomValues(new Uint8Array(32));
  const v = new Vault(sealed(raw, async () => key));
  assert.equal((await v.load()).data.sessions.length, 2);
  assert.ok((await raw.get(KEY)).startsWith('{"enc":1,') && !(await raw.get(KEY)).includes("keepme"));
});

test("data key is created once in the secure store and reused", async () => {
  const sec = new Map(), secure = { get: async (k) => sec.get(k) || null, set: async (k, v) => void sec.set(k, v) };
  const k1 = await keyFromSecureStore(secure)(), k2 = await keyFromSecureStore(secure)();
  assert.equal(k1.length, 32);
  assert.deepEqual([...k1], [...k2]);
});
