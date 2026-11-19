// Runs the rewards engine exactly as it ships, taken from web/index.html between the REWARDS markers.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const RW = new Function(html.slice(html.indexOf("/* REWARDS-START"), html.indexOf("/* REWARDS-END */")) + "\nreturn RW;")();

const DAY = 864e5, T0 = new Date(2026, 10, 2, 12).getTime();          // a Monday, local noon
let n = 0;
const mem = (o = {}) => ({ id: "m" + ++n, kind: "done", title: "Memory " + n, date: T0, createdAt: T0, cat: "dinner", location: "", ...o });
const ses = (o = {}) => ({ id: "s" + ++n, start: T0, durationSec: 1200, createdAt: T0, ...o });
const pts = (d, f) => RW.compute({ exps: [], sessions: [], rewards: {}, ...d }, f);
const key = (r, k) => r.awards.find((a) => a.k === k);

test("a memory earns points, and its first-of-a-kind bonus once", () => {
  const r = pts({ exps: [mem({ cat: "dinner" }), mem({ cat: "dinner", createdAt: T0 + DAY, date: T0 + DAY })] });
  assert.equal(r.earned, 20 + 50 + 20);
  assert.equal(r.awards.filter((a) => a.k === "kind:dinner").length, 1);
});

test("the same record can never be awarded twice, even if it appears more than once", () => {
  const e = mem(), s = ses();
  const r = pts({ exps: [e, { ...e }, { ...e }], sessions: [s, { ...s }] });
  assert.equal(r.earned, 20 + 50 + 10);
  assert.equal(new Set(r.awards.map((a) => a.k)).size, r.awards.length);
});

test("anti-spam: at most 3 memories a day earn points; the rest are listed as not counted", () => {
  const r = pts({ exps: Array.from({ length: 6 }, () => mem({ createdAt: T0 + 1000 })) });
  const m = r.awards.filter((a) => a.k.startsWith("exp:"));
  assert.equal(m.filter((a) => a.vp > 0).length, 3);
  assert.equal(m.filter((a) => a.capped).length, 3);
});

test("deleting a record takes its points back, so create-and-delete earns nothing", () => {
  const e = mem();
  assert.equal(pts({ exps: [e] }).earned, 70);
  assert.equal(pts({ exps: [] }).earned, 0);
});

test("demo data, plans not yet done and broken records earn nothing", () => {
  assert.equal(pts({ exps: [mem({ demo: true }), mem({ kind: "plan" }), { id: "x", kind: "done", date: "soon" }, null], sessions: [ses({ demo: true })] }).earned, 0);
});

test("completing a planned date earns 75, a shared plan earns 100 instead", () => {
  const r = pts({ exps: [mem({ planned: true, doneAt: T0, cat: "trip" }), mem({ planned: true, doneAt: T0, cat: "trip", space: "sp1" })] });
  const plans = r.awards.filter((a) => a.k.startsWith("plan:")).map((a) => a.vp).sort();
  assert.deepEqual(plans, [100, 75]);
});

test("intimacy: once a week whatever the frequency, duration or head count", () => {
  const many = Array.from({ length: 7 }, (_, i) => ses({ createdAt: T0 + i * 3600e3, durationSec: 600 * (i + 1), category: i % 2 ? "poly" : "couple", participants: i % 2 ? 6 : 2 }));
  const one = [ses()];
  assert.equal(pts({ sessions: many }).earned, pts({ sessions: one }).earned);
  assert.equal(pts({ sessions: one }).earned, 10);
  const twoWeeks = [ses(), ses({ createdAt: T0 + 7 * DAY })];
  assert.equal(pts({ sessions: twoWeeks }).earned, 20);
});

test("intimacy: a mutually confirmed session makes that week 20 in total, and never says what it was", () => {
  const s = ses({ title: "PRIVATE", notes: "SECRET" });
  const r = pts({ sessions: [s, ses()] }, (x) => x.id === s.id);
  assert.equal(r.earned, 20);
  for (const a of r.awards) { assert.ok(a.private); assert.ok(!/PRIVATE|SECRET|Couple|Poly|min/.test(a.why), a.why); }
});

test("weekly challenge: valid only with a qualifying memory from that week, once a week", () => {
  const w = RW.week(T0), e = mem({ cat: "dinner", location: "Corner bistro" });
  const ok = pts({ exps: [e], rewards: { ch: { [w]: { cid: "newrest", expId: e.id } } } });
  assert.equal(key(ok, "ch:" + w).vp, 150);
  const wrongKind = mem({ cat: "trip", location: "Somewhere" });
  assert.equal(key(pts({ exps: [wrongKind], rewards: { ch: { [w]: { cid: "newrest", expId: wrongKind.id } } } }), "ch:" + w), undefined);
  const oldWeek = mem({ cat: "dinner", location: "Elsewhere", createdAt: T0 - 7 * DAY, date: T0 - 7 * DAY });
  assert.equal(key(pts({ exps: [oldWeek], rewards: { ch: { [w]: { cid: "newrest", expId: oldWeek.id } } } }), "ch:" + w), undefined, "a memory from another week doesn't count");
  assert.equal(key(pts({ exps: [], rewards: { ch: { [w]: { cid: "newrest", expId: e.id } } } }), "ch:" + w), undefined, "deleting the memory voids the challenge");
});

test("'somewhere new' really means a place not logged before", () => {
  const before = mem({ location: "The Pier", createdAt: T0 - 30 * DAY, date: T0 - 30 * DAY }), again = mem({ location: "the pier ", createdAt: T0 });
  assert.equal(RW.qualifies(RW.CH.newplace, again, [before, again]), false);
  assert.equal(RW.qualifies(RW.CH.newplace, mem({ location: "Hilltop" }), [before]), true);
  assert.equal(RW.qualifies(RW.CH.newplace, mem({ location: "" }), [before]), false);
});

test("challenges are about experiences only, follow preferences and stay the same all week", () => {
  assert.ok(RW.CHALLENGES.every((c) => !/intima|sex|session|bed/i.test(c.t + c.d)));
  const w = RW.week(T0);
  assert.deepEqual(RW.challengesFor(w).map((c) => c.id), RW.challengesFor(w).map((c) => c.id));
  assert.ok(RW.challengesFor(w, { budget: 0 }).every((c) => c.b === 0));
  assert.ok(RW.challengesFor(w, { lowEnergy: true }).every((c) => c.e <= 1));
  assert.ok(RW.challengesFor(w, { interests: ["food"] }).some((c) => c.g.includes("food")));
});

test("badges: earned, with progress toward the ones still locked", () => {
  const trips = Array.from({ length: 5 }, (_, i) => mem({ cat: "trip", title: "Trip " + i, createdAt: T0 + i * DAY, date: T0 + i * DAY }));
  const r = pts({ exps: trips });
  const b = Object.fromEntries(r.badges.map((x) => [x.id, x]));
  assert.ok(b.spark.earnedAt && b.wander.earnedAt);
  assert.equal(b.wander.earnedAt, T0 + 4 * DAY);
  assert.deepEqual([b.explorers.have, b.explorers.earnedAt], [5, null]);
  assert.equal(b.chapter.earnedAt, null, "a milestone has to be shared to count");
});

test("levels rise with points earned; spending doesn't lower them", () => {
  assert.equal(RW.level(0).name, "Spark");
  assert.deepEqual([RW.level(260).n, RW.level(260).name, RW.level(260).next], [3, "Ember", 450]);
  const r = pts({ exps: [mem()], rewards: { spent: [{ cost: 50 }] } });
  assert.deepEqual([r.earned, r.balance, r.level.at], [70, 20, 0]);
  assert.equal(pts({ exps: [], rewards: { spent: [{ cost: 50 }] } }).balance, 0, "balance never goes below zero");
});
