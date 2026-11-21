// Daily Forecast engine exactly as it ships in web/index.html: consistency, honesty about thin data, and safety filters.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const code = html.slice(html.indexOf("const FC_WORDS="), html.indexOf("async function fcPublish("));
const IDEAS = [{ id: "walk", t: "Sunset walk", g: ["outdoors", "romance"] }, { id: "cook", t: "Cook together", g: ["food", "home"] }, { id: "climb", t: "Climbing", g: ["adventure"] }];
const IDEA = Object.fromEntries(IDEAS.map((x) => [x.id, x]));
const F = new Function("IDEAS", "IDEA", "SAMPLE", "S", "num", code + "\nreturn {fcBuild,fcDims,fcWord,fcSeed,fcClean,fcSafe,FC_WORDS,FC_NEW,FC_TOGETHER};")(
  IDEAS, IDEA, null, { fc: {} }, (v) => (typeof v === "number" && isFinite(v) ? v : null));
const none = { checkins: [], memories: [], moods: [], observed: [], mismatch: false };
const rich = { checkins: [{ energy: "Tender", close: 5, wants: ["closeness"] }, { energy: "Reflective", close: 4, wants: ["talk"] }],
  memories: [{ cat: "romantic", mood: "Connected" }, { cat: "dinner", mood: "Tender" }], moods: [], observed: ["2 shared memories"], mismatch: false };

test("same couple, same day, same inputs: the same forecast on every device", () => {
  const a = F.fcBuild("pair|x|y|2026-11-21", rich, [], [], false), b = F.fcBuild("pair|x|y|2026-11-21", rich, [], [], false);
  assert.deepEqual({ ...a, at: 0 }, { ...b, at: 0 });
});

test("a new couple gets an opening word and no invented energies", () => {
  const f = F.fcBuild("solo|me|2026-11-21", none, [], [], false);
  assert.ok(F.FC_NEW.includes(f.word));
  assert.ok(Object.values(f.dims).every((v) => v === null), "unknown stays unknown");
  assert.equal(f.sections.connection.basis, "reflection");
});

test("the word follows the evidence", () => {
  const f = F.fcBuild("s|2026-11-21", rich, [], [], false);
  assert.ok(f.dims.in > 0.7, "closeness check-ins raise intimacy");
  assert.ok(["TENDER", "INTIMATE", "DEVOTED", "UNGUARDED", "WARM", "GENTLE", "SERENE", "ALIGNED"].includes(f.word), f.word);
  assert.equal(f.sections.connection.basis, "observed");
});

test("recent words aren't repeated, and rejected words are leaned away from", () => {
  const first = F.fcBuild("s|d1", rich, [], [], false).word;
  assert.notEqual(F.fcBuild("s|d1", rich, [first], [], false).word, first);
  let shifted = 0;
  for (let i = 0; i < 20; i++) { const d = "s|d" + i, w = F.fcBuild(d, rich, [], [], false).word; if (F.fcBuild(d, rich, [], [w], false).word !== w) shifted++; }
  assert.ok(shifted >= 5, "a rejection moves the choice often enough to matter");
});

test("different days vary", () => {
  const ws = new Set(); for (let i = 1; i <= 14; i++) ws.add(F.fcBuild("s|2026-11-" + i, { ...rich, checkins: [] }, [], [], false).word);
  assert.ok(ws.size >= 2);
});

test("intimacy ideas appear only when asked for", () => {
  assert.equal(F.fcBuild("s|d", rich, [], [], false).move.close, null);
  assert.ok(F.fcBuild("s|d", rich, [], [], true).move.close);
});

test("AI text that predicts, diagnoses, gets explicit or links out is thrown away", () => {
  const base = F.fcBuild("s|d", rich, [], [], false), good = { connection: "You've been choosing each other in small ways.", embrace: "Ask the question you've been saving tonight.", watch: "A short reply isn't always a cold one." };
  assert.equal(F.fcClean(good, base).src, "ai");
  for (const bad of ["This week you will definitely fight.", "Your partner shows narcissist traits here.", "Tonight's sex will be amazing.", "Read more at https://x.example", "The stars align for you two."])
    assert.equal(F.fcClean({ ...good, watch: bad }, base), null, bad);
  assert.equal(F.fcClean({ connection: "too short" }, base), null);
});

test("a partner's forecast is accepted only in the known shape", () => {
  const x = F.fcSafe({ word: "<script>", line: "x", dims: { ch: 7, co: "a", in: 0.4 }, sections: { connection: { t: "ok text here", basis: "evil" } }, move: { t: "m", qs: ["not one of ours"], ideas: ["walk", "nope"] }, extra: "secret", src: "ai" });
  assert.equal(x.word, "UNWRITTEN"); assert.equal(x.dims.ch, 1); assert.equal(x.dims.co, null); assert.equal(x.sections.connection.basis, "suggestion");
  assert.deepEqual(x.move.qs, []); assert.deepEqual(x.move.ideas, ["walk"]); assert.equal(x.move.close, null); assert.equal(x.extra, undefined);
});

test("together pulse compares energies without judging them", () => {
  assert.equal(F.FC_TOGETHER("Tender", "Close").w, "IN SYNC");
  assert.equal(F.FC_TOGETHER("Restless", "Tired").w, "CONTRAST");
  assert.equal(F.FC_TOGETHER("Playful", null), null);
});
