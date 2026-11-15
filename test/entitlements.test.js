import test from "node:test";
import assert from "node:assert/strict";
import { resolve, can, FEATURES, PRODUCTS, validateServerRecord, OFFLINE_TRUST_MS } from "../core/entitlements.js";

const NOW = 1_800_000_000_000, DAY = 864e5;
const rec = (o = {}) => ({ productId: "vouz.plus.monthly", status: "active", expiresAt: NOW + 20 * DAY, verifiedAt: NOW - DAY, environment: "production", originalTransactionId: "t1", ...o });

test("no record means Free, and Free keeps all core tracking", () => {
  const e = resolve(null, NOW);
  assert.deepEqual([e.plan, e.active], ["free", false]);
  for (const f of ["tracking", "manualLog", "history", "replay", "weeklyStreaks", "basicInsights", "journal", "privacyControls", "export", "deleteAccount"]) assert.equal(can(f, e), true, f);
  for (const f of ["advancedInsights", "extendedComparisons", "customThemes"]) assert.equal(can(f, e), false, f);
});

test("a verified active subscription unlocks Plus features", () => {
  const e = resolve(rec(), NOW);
  assert.deepEqual([e.plan, e.active, e.simulated], ["plus", true, false]);
  assert.ok(Object.keys(FEATURES).every((f) => can(f, e)));
  assert.equal(resolve(rec({ productId: "vouz.plus.annual" }), NOW).active, true);
});

test("expiry, refund and revocation all fall back to Free", () => {
  assert.equal(resolve(rec({ expiresAt: NOW - 1 }), NOW).reason, "expired");
  assert.equal(resolve(rec({ status: "expired" }), NOW).active, false);
  assert.equal(resolve(rec({ status: "refunded" }), NOW).reason, "refunded");
  assert.equal(resolve(rec({ status: "revoked" }), NOW).reason, "revoked");
  assert.equal(resolve(rec({ productId: "something.else" }), NOW).reason, "none");
});

test("billing grace period keeps access until it ends", () => {
  const g = rec({ status: "grace", expiresAt: NOW - DAY, graceUntil: NOW + 3 * DAY });
  assert.deepEqual([resolve(g, NOW).active, resolve(g, NOW).reason], [true, "grace"]);
  assert.equal(resolve(g, NOW + 4 * DAY).active, false);
});

test("offline: trusted for a week after the last check, then asks to verify, never past expiry", () => {
  assert.equal(resolve(rec({ verifiedAt: NOW - 6 * DAY }), NOW).active, true);
  const stale = resolve(rec({ verifiedAt: NOW - OFFLINE_TRUST_MS - 1 }), NOW);
  assert.deepEqual([stale.active, stale.reason, stale.stale], [false, "needs-verification", true]);
});

test("simulated purchases never count in a production build and are always labelled", () => {
  assert.equal(resolve(rec({ environment: "mock" }), NOW).reason, "mock-not-allowed");
  assert.equal(resolve(rec({ environment: "sandbox" }), NOW).reason, "sandbox-not-allowed");
  const dev = resolve(rec({ environment: "mock" }), NOW, { allowMock: true });
  assert.deepEqual([dev.active, dev.simulated], [true, true]);
  assert.equal(resolve(rec({ environment: "sandbox" }), NOW, { allowSandbox: true }).simulated, true);
});

test("server record validation and proposed prices", () => {
  assert.deepEqual(validateServerRecord(rec()), []);
  assert.deepEqual(validateServerRecord({ productId: "x", status: "paid", environment: "prod" }), ["unknown product", "bad status", "bad environment", "missing expiry", "missing transaction id"]);
  assert.deepEqual([PRODUCTS["vouz.plus.monthly"].proposedUsd, PRODUCTS["vouz.plus.annual"].proposedUsd], [3.99, 29.99]);
});
