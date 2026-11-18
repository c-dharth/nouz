// Thin Supabase client for sync. Uses fetch against the project's REST endpoints, so there is no SDK to install.
// Configuration comes from the build environment (see .env.example). With no configuration the app runs local-only.
import { drain, mergeSessions } from "./sync.js";

export function configFrom(env = {}) {
  const url = env.VITE_SUPABASE_URL || env.SUPABASE_URL || "", key = env.VITE_SUPABASE_ANON_KEY || env.SUPABASE_ANON_KEY || "";
  if (!url || !key) return null;                                   // cloud is optional
  if (!/^https:\/\//.test(url)) throw new Error("SUPABASE_URL must be https.");
  if (/service_role/.test(key) || env.SUPABASE_SERVICE_ROLE_KEY && key === env.SUPABASE_SERVICE_ROLE_KEY) throw new Error("Never ship the service role key in the app.");
  return { url: url.replace(/\/$/, ""), key };
}

export function backend(cfg, getToken, fetchImpl = globalThis.fetch) {
  const call = async (path, init = {}) => {
    const token = await getToken();
    if (!token) throw Object.assign(new Error("signed out"), { retryable: true });
    let res;
    try { res = await fetchImpl(cfg.url + path, { ...init, headers: { apikey: cfg.key, Authorization: "Bearer " + token, "Content-Type": "application/json", ...(init.headers || {}) } }); }
    catch (e) { throw Object.assign(new Error("offline"), { retryable: true }); }
    if (res.ok) return res.status === 204 ? null : res.json();
    // 401 = token expired (retry after refresh); 5xx / 429 = try later; other 4xx = the server will never accept this.
    throw Object.assign(new Error("http " + res.status), { retryable: res.status === 401 || res.status === 429 || res.status >= 500, status: res.status });
  };
  const toRow = (s, deletedAt) => ({ id: s.id, start: s.start, durationSec: s.durationSec, segments: s.segments ?? null, category: s.category ?? null, participants: s.participants ?? null, satisfaction: s.satisfaction ?? null, sharedNote: s.sharedNote || "",
    title: s.title || "", tags: s.tags || [], mood: s.mood || "", hrAvg: s.hrAvg || "", hrPeak: s.hrPeak || "", updatedAt: s.updatedAt || Date.now(), ...(deletedAt ? { deletedAt } : {}) });
  const fromRow = (r) => ({ id: r.id, start: Date.parse(r.started_at), durationSec: r.duration_sec, segments: r.segments, category: r.category, participants: r.participants ?? null, satisfaction: r.satisfaction ?? null, sharedNote: r.shared_note || "", title: r.title,
    tags: r.tags || [], mood: r.mood || "", hrAvg: r.hr_avg == null ? "" : String(r.hr_avg), hrPeak: r.hr_peak == null ? "" : String(r.hr_peak), updatedAt: +r.client_updated_at, _deletedAt: r.deleted_at ? Date.parse(r.deleted_at) : null });
  return {
    // Notes travel separately from the session row and are never part of anything shared.
    async push(op, data) {
      if (op.kind === "settings") return call("/rest/v1/user_settings?on_conflict=user_id", { method: "POST", headers: { Prefer: "resolution=merge-duplicates" }, body: JSON.stringify({ user_id: op.userId, data: data.settings }) });
      const s = data.sessions.find((x) => x.id === op.id);
      if (op.kind === "delete" || !s) return call("/rest/v1/rpc/upsert_session", { method: "POST", body: JSON.stringify({ s: { id: op.id, start: 0, durationSec: 1, updatedAt: op.at, deletedAt: op.at } }) });
      if (s.demo) return null;
      await call("/rest/v1/rpc/upsert_session", { method: "POST", body: JSON.stringify({ s: toRow(s) }) });
      return call("/rest/v1/session_notes?on_conflict=user_id,session_id", { method: "POST", headers: { Prefer: "resolution=merge-duplicates" }, body: JSON.stringify({ user_id: op.userId, session_id: s.id, notes: s.notes || "", reflection: s.reflection || "" }) });
    },
    async pull() {
      const rows = await call("/rest/v1/sessions?select=*"), notes = await call("/rest/v1/session_notes?select=session_id,notes,reflection");
      const n = Object.fromEntries(notes.map((x) => [x.session_id, x])), sessions = [], deleted = {};
      for (const r of rows.map(fromRow)) { if (r._deletedAt) { deleted[r.id] = r._deletedAt; continue; } delete r._deletedAt; sessions.push({ ...r, notes: n[r.id]?.notes || "", reflection: n[r.id]?.reflection || "" }); }
      return { sessions, deleted };
    },
    exportAll: () => call("/rest/v1/rpc/export_my_data", { method: "POST", body: "{}" }),
    deleteAccount: () => call("/functions/v1/delete-account", { method: "POST", body: "{}" }),
    entitlement: async () => (await call("/rest/v1/entitlements?select=*"))[0] || null,
  };
}

// One sync pass: send what is queued, then fold in what the server has. Safe to call at any time; does nothing useful offline and loses nothing.
export async function syncOnce(data, queue, api, now = Date.now()) {
  const sent = await drain(queue, (op) => api.push(op, data), now);
  if (sent.offline) return { data, queue: sent.queue, status: "offline", rejected: sent.rejected, conflicts: [] };
  let remote;
  try { remote = await api.pull(); } catch (e) { return { data, queue: sent.queue, status: "offline", rejected: sent.rejected, conflicts: [] }; }
  const local = data.sessions.filter((s) => !s.demo), m = mergeSessions(local, remote.sessions, data.deleted, remote.deleted);
  return { data: { ...data, sessions: m.sessions.concat(data.sessions.filter((s) => s.demo)), deleted: m.deleted }, queue: sent.queue, status: "ok", rejected: sent.rejected, conflicts: m.conflicts };
}
