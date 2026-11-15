// VOUZ Plus entitlements. The app never decides on its own that someone has paid:
// it reads an entitlement record that the server wrote after verifying a receipt with Apple or Google.
// Prices are proposals and are shown from the store at runtime, not from this file.

export const PRODUCTS = {
  "vouz.plus.monthly": { plan: "plus", period: "month", proposedUsd: 3.99 },
  "vouz.plus.annual": { plan: "plus", period: "year", proposedUsd: 29.99 },
};

// Core tracking is never gated.
export const FEATURES = {
  tracking: "free", manualLog: "free", history: "free", replay: "free", weeklyStreaks: "free", basicInsights: "free",
  journal: "free", privacyControls: "free", export: "free", deleteAccount: "free", social: "free",
  advancedInsights: "plus", extendedComparisons: "plus", customThemes: "plus",
};

export const OFFLINE_TRUST_MS = 7 * 864e5;   // how long a verified record is trusted without re-checking

// record: { productId, status, expiresAt, verifiedAt, environment } as stored by the server, or null.
// env:    { allowSandbox, allowMock } from build configuration. Mock purchases only count in a labelled dev build.
export function resolve(record, now = Date.now(), env = {}) {
  const free = (reason) => ({ plan: "free", active: false, reason, expiresAt: null, simulated: false });
  if (!record || !PRODUCTS[record.productId]) return free("none");
  const e = record.environment || "production";
  if (e === "mock" && !env.allowMock) return free("mock-not-allowed");
  if (e === "sandbox" && !env.allowSandbox && !env.allowMock) return free("sandbox-not-allowed");
  if (record.status === "revoked" || record.status === "refunded") return free(record.status);
  const exp = +record.expiresAt || 0;
  const inGrace = record.status === "grace" && now < (+record.graceUntil || 0);
  if (!(record.status === "active" && now < exp) && !inGrace) return free("expired");
  // Offline: keep honouring a record we verified recently, never past its own expiry.
  if (now - (+record.verifiedAt || 0) > OFFLINE_TRUST_MS && e === "production") return { ...free("needs-verification"), stale: true };
  return { plan: "plus", active: true, reason: inGrace ? "grace" : "active", expiresAt: inGrace ? +record.graceUntil : exp, simulated: e !== "production", willRenew: record.willRenew !== false };
}

export const can = (feature, ent) => FEATURES[feature] === "free" || (FEATURES[feature] === "plus" && !!ent && ent.active);

// What the server must check before writing a record (mirrored in supabase/functions/verify-entitlement).
export function validateServerRecord(r) {
  const errs = [];
  if (!r || !PRODUCTS[r.productId]) errs.push("unknown product");
  if (!["active", "grace", "expired", "revoked", "refunded"].includes(r?.status)) errs.push("bad status");
  if (!["production", "sandbox", "mock"].includes(r?.environment)) errs.push("bad environment");
  if (!(+r?.expiresAt > 0)) errs.push("missing expiry");
  if (!r?.originalTransactionId) errs.push("missing transaction id");
  return errs;
}
