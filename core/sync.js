// Offline-first sync: local changes go into a durable queue and are pushed when a connection exists.
// Tracking never waits on the network. Conflicts resolve per session: the newer `updatedAt` wins, and a
// deletion beats any copy that is not newer than it.

export function enqueue(queue, op) {
  // op: { kind: "upsert"|"delete"|"settings", id, at }. Later ops on the same record replace earlier ones.
  const out = queue.filter((q) => !(q.kind !== "settings" && op.kind !== "settings" && q.id === op.id) && !(q.kind === "settings" && op.kind === "settings"));
  out.push({ tries: 0, ...op });
  return out;
}

export function mergeSessions(local, remote, localDeleted = {}, remoteDeleted = {}) {
  const deleted = { ...remoteDeleted };
  for (const k in localDeleted) deleted[k] = Math.max(deleted[k] || 0, localDeleted[k]);
  const byId = new Map();
  for (const s of [...remote, ...local]) {
    const c = byId.get(s.id);
    if (!c || (s.updatedAt || 0) > (c.updatedAt || 0)) byId.set(s.id, s);
  }
  const sessions = [...byId.values()].filter((s) => !(deleted[s.id] >= (s.updatedAt || 0)));
  const conflicts = [];
  for (const l of local) { const r = remote.find((x) => x.id === l.id); if (r && (r.updatedAt || 0) !== (l.updatedAt || 0)) conflicts.push({ id: l.id, kept: (r.updatedAt || 0) > (l.updatedAt || 0) ? "remote" : "local" }); }
  return { sessions, deleted, conflicts };
}

const backoffMs = (tries) => Math.min(15 * 60000, 2000 * 2 ** tries);

// push(op) resolves on success; rejects with { retryable: boolean }.
// Stops at the first retryable failure so order is preserved; drops ops the server permanently refuses and reports them.
export async function drain(queue, push, now = Date.now()) {
  const left = [], rejected = [];
  let sent = 0, blocked = false;
  for (const op of queue) {
    if (blocked || (op.notBefore || 0) > now) { left.push(op); blocked = true; continue; }
    try { await push(op); sent++; }
    catch (e) {
      if (e && e.retryable === false) rejected.push({ op, reason: e.message || "refused" });
      else { left.push({ ...op, tries: op.tries + 1, notBefore: now + backoffMs(op.tries) }); blocked = true; }
    }
  }
  return { queue: left, sent, rejected, offline: blocked };
}
