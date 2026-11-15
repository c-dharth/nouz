// VOUZ persistence layer.
// One interface, several backends: browser localStorage today, a native key-value store on iOS and Android,
// and an in-memory store for tests. The app talks to `Vault`, never to a backend directly.
//
// Honest scope: a plain adapter stores readable JSON. Only `sealed()` encrypts, and it is only as strong as
// the place its key is kept. On a phone that must be the Keychain / Android Keystore (see keyFromSecureStore);
// that part cannot be verified without a device build and is marked pending.

export const KEY = "vouz.v1";                 // unchanged, so existing data is picked up as is
export const SCHEMA = 2;                      // internal shape version, stored as `schema`; `v` stays 1 for sync compatibility

const CATS = ["solo", "duo", "trio", "group", "partnered"];

// ---- adapters: async get / set / remove over strings ----
export const memoryAdapter = (init = {}) => {
  const m = new Map(Object.entries(init));
  return { get: async (k) => (m.has(k) ? m.get(k) : null), set: async (k, v) => void m.set(k, String(v)), remove: async (k) => void m.delete(k), keys: async () => [...m.keys()], _map: m };
};
export const localStorageAdapter = (ls = globalThis.localStorage) => ({
  get: async (k) => ls.getItem(k), set: async (k, v) => ls.setItem(k, v), remove: async (k) => ls.removeItem(k),
  keys: async () => Array.from({ length: ls.length }, (_, i) => ls.key(i)),
});
// Capacitor Preferences (UserDefaults / SharedPreferences). Pass the plugin in; nothing is imported here.
export const preferencesAdapter = (Preferences) => ({
  get: async (k) => (await Preferences.get({ key: k })).value ?? null,
  set: async (k, v) => Preferences.set({ key: k, value: v }),
  remove: async (k) => Preferences.remove({ key: k }),
  keys: async () => (await Preferences.keys()).keys,
});

// ---- encryption at rest (AES-256-GCM via WebCrypto) ----
const b64 = (u) => { let s = ""; new Uint8Array(u).forEach((b) => (s += String.fromCharCode(b))); return btoa(s); };
const ub64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
const te = new TextEncoder(), td = new TextDecoder();

// keySource: async () => 32 raw bytes. Values written before sealing was on are still readable, and are sealed on the next save.
export function sealed(adapter, keySource) {
  let key;
  const k = async () => key || (key = await crypto.subtle.importKey("raw", await keySource(), "AES-GCM", false, ["encrypt", "decrypt"]));
  return {
    ...adapter,
    encrypted: true,
    async get(name) {
      const raw = await adapter.get(name);
      if (raw === null || !raw.startsWith('{"enc":1,')) return raw;
      const o = JSON.parse(raw);
      const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: ub64(o.iv), additionalData: te.encode(name) }, await k(), ub64(o.ct));
      return td.decode(pt);
    },
    async set(name, value) {
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: te.encode(name) }, await k(), te.encode(value));
      return adapter.set(name, JSON.stringify({ enc: 1, iv: b64(iv), ct: b64(ct) }));
    },
  };
}
// Key kept in the platform secure store (Keychain / Keystore) through a secure-storage plugin that exposes get/set.
// PENDING NATIVE VERIFICATION: which plugin, its accessibility class, and behaviour after device restore.
export const keyFromSecureStore = (secure, name = "vouz.dek") => async () => {
  let v = await secure.get(name);
  if (!v) { v = b64(crypto.getRandomValues(new Uint8Array(32))); await secure.set(name, v); }
  return ub64(v);
};

// ---- data shape ----
export const fresh = () => ({
  v: 1, schema: SCHEMA, onboarded: false, stamp: 0, user: { name: "", mode: "local", createdAt: Date.now() },
  settings: { social: false, privateProfile: true, defaultVis: "connections", regular: null, pinHash: null, pinSalt: null, showStreak: false },
  sessions: [], deleted: {}, active: null, draft: null, blocks: [], ignored: [],
});

// Each migration takes data at schema n and returns schema n+1. They must be safe to run on partial data.
export const MIGRATIONS = {
  // 1 -> 2: categories beyond solo/partnered, optional group size, people on a session, streak visibility.
  // "partnered" is left exactly as it is; it is never rewritten as Duo.
  1: (d) => {
    d.sessions = (Array.isArray(d.sessions) ? d.sessions : []).filter((s) => s && typeof s.start === "number" && s.durationSec > 0).map((s) => ({
      ...s,
      id: String(s.id),
      category: CATS.includes(s.category) ? s.category : null,
      groupSize: s.category === "group" && +s.groupSize >= 4 ? Math.min(99, Math.round(+s.groupSize)) : null,
      tags: Array.isArray(s.tags) ? s.tags : [],
      people: Array.isArray(s.people) ? s.people : [],
    }));
    d.deleted = d.deleted && typeof d.deleted === "object" ? d.deleted : {};
    d.settings = { ...fresh().settings, ...(d.settings || {}) };
    if (d.active && !("category" in d.active)) d.active.category = null;
    return d;
  },
};

export function migrate(data) {
  let d = data, from = d.schema || 1;
  if (from > SCHEMA) throw Object.assign(new Error("Data was written by a newer version of VOUZ."), { code: "newer" });
  for (let n = from; n < SCHEMA; n++) { d = MIGRATIONS[n](d); d.schema = n + 1; }
  return { data: d, from, migrated: from !== SCHEMA };
}

const looksValid = (o) => o && typeof o === "object" && o.v === 1 && Array.isArray(o.sessions);

// ---- the vault ----
// Writes go: new value -> KEY.next, then the current good value -> KEY.bak, then new value -> KEY, then drop KEY.next.
// A crash at any point leaves at least one complete, parseable copy. load() walks them in order of freshness.
export class Vault {
  constructor(adapter) { this.a = adapter; this.q = Promise.resolve(); }

  // Everything that touches storage runs through one queue, so a load, a save and an update can never interleave.
  _queue(fn) { const p = this.q.then(fn, fn); this.q = p.catch(() => {}); return p; }
  load() { return this._queue(() => this._load()); }
  save(data) { return this._queue(() => this._write(data)); }
  // Read, change, write as one step.
  update(fn) { return this._queue(async () => { const { data } = await this._load(); const out = (await fn(data)) || data; out.stamp = Date.now(); await this._write(out); return out; }); }

  async _load() {
    const report = { source: null, recovered: false, migratedFrom: null, quarantined: null, error: null };
    for (const name of [KEY + ".next", KEY, KEY + ".bak"]) {
      let raw;
      try { raw = await this.a.get(name); } catch (e) { report.error = "unreadable"; continue; }
      if (raw === null || raw === undefined) continue;
      let o;
      try { o = JSON.parse(raw); } catch (e) { o = null; }
      if (!looksValid(o)) {
        // Keep the damaged bytes rather than deleting them: someone may be able to rescue them later.
        if (name === KEY && !report.quarantined) { report.quarantined = KEY + ".corrupt." + Date.now(); try { await this.a.set(report.quarantined, raw); } catch (e) {} }
        continue;
      }
      // Keep an untouched copy before the first migration of old data.
      if ((o.schema || 1) < SCHEMA) { try { await this.a.set(KEY + ".pre" + SCHEMA, raw); } catch (e) {} }
      const m = migrate(o);
      report.source = name; report.recovered = name !== KEY; report.migratedFrom = m.migrated ? m.from : null;
      if (m.migrated || report.recovered) await this._write(m.data);
      return { data: m.data, report };
    }
    return { data: fresh(), report };
  }

  async _write(data) {
    const next = JSON.stringify(data);
    if (!looksValid(JSON.parse(next))) throw new Error("Refusing to save data that would not load again.");
    await this.a.set(KEY + ".next", next);
    let cur = null;
    try { cur = await this.a.get(KEY); } catch (e) {}
    if (cur !== null) { try { if (looksValid(JSON.parse(cur))) await this.a.set(KEY + ".bak", cur); } catch (e) {} }
    await this.a.set(KEY, next);
    await this.a.remove(KEY + ".next");
  }

  // Export never includes demo rows, the screen-lock hash, or social keys.
  static exportOf(data) {
    const { pinHash, pinSalt, pinAlg, ...settings } = data.settings || {};
    return { app: "vouz", v: 1, schema: SCHEMA, exportedAt: new Date().toISOString(), user: { name: data.user?.name || "" }, settings, sessions: (data.sessions || []).filter((s) => !s.demo), deleted: data.deleted || {} };
  }

  // Import adds what is missing and never overwrites or deletes what is already here.
  static importInto(data, file) {
    if (!file || !Array.isArray(file.sessions)) throw Object.assign(new Error("Not a VOUZ export."), { code: "format" });
    const incoming = migrate({ v: 1, schema: file.schema || 1, sessions: file.sessions, settings: {}, deleted: {} }).data.sessions;
    const have = new Set(data.sessions.map((s) => s.id));
    let added = 0;
    for (const s of incoming) { if (s.demo || have.has(s.id)) continue; data.sessions.push({ ...s, updatedAt: Date.now() }); delete data.deleted[s.id]; have.add(s.id); added++; }
    return { data, added, skipped: incoming.length - added };
  }

  // Deletion wipes every copy, including backups and quarantined files.
  async wipe() {
    const names = this.a.keys ? (await this.a.keys()).filter((k) => k === KEY || k.startsWith(KEY + ".")) : [KEY, KEY + ".bak", KEY + ".next"];
    for (const n of names) await this.a.remove(n);
  }
}
