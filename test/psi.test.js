// Runs the Mutual Match code exactly as it ships, taken from web/index.html between the PSI markers.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const src = html.slice(html.indexOf("/* PSI-START"), html.indexOf("/* PSI-END */"));
const PSI = new Function(src + "\nreturn PSI;")();

// Simulate each person opening the app in turn until nothing changes, as the app does on every storage update.
async function run(tag, picks) {
  const members = Object.keys(picks).sort(), st = {}, docs = {};
  for (const u of members) { const k = PSI.newKey(); st[u] = { k, ...(await PSI.own(tag, picks[u], k)) }; docs[u] = { own: st[u].vals, fwd: {} }; }
  for (let round = 0; round < members.length + 1; round++)
    for (const u of members) docs[u].fwd = await PSI.forward(members, u, docs, st[u].k, docs[u].fwd);
  const fin = await PSI.finals(members, docs);
  return { members, docs, st, fin, result: Object.fromEntries(members.map((u) => [u, PSI.matches(members, u, fin, st[u].order)])) };
}

test("the group is the 2048-bit safe prime from RFC 3526", () => {
  assert.equal(PSI.P.toString(2).length, 2048);
});

test("two people: only ideas both picked are revealed, to both", async () => {
  const r = await run("tag1", { alice: ["hike", "cook", "picnic"], bob: ["cook", "picnic", "museum"] });
  assert.deepEqual(r.result.alice.sort(), ["cook", "picnic"]);
  assert.deepEqual(r.result.bob.sort(), ["cook", "picnic"]);
});

test("three people: only what all three picked", async () => {
  const r = await run("tag2", { a: ["hike", "cook", "picnic"], b: ["cook", "picnic", "museum"], c: ["cook", "museum", "stars"] });
  for (const u of ["a", "b", "c"]) assert.deepEqual(r.result[u], ["cook"], u);
});

test("nothing in common means no matches; nobody sees anything", async () => {
  const r = await run("tag3", { a: ["hike"], b: ["cook"] });
  assert.deepEqual([r.result.a, r.result.b], [[], []]);
});

test("what is shared contains no idea names and hides how many were picked", async () => {
  const r = await run("tag4", { a: ["hike"], b: ["cook", "picnic", "museum", "stars", "bike"] });
  const wire = JSON.stringify(r.docs);
  for (const w of ["hike", "cook", "picnic", "museum"]) assert.ok(!wire.includes(w));
  assert.equal(r.docs.a.own.length, PSI.CAP);
  assert.equal(r.docs.b.own.length, PSI.CAP, "both sets are padded to the same size");
});

test("the same idea looks different for different people and different spaces", async () => {
  const a = await PSI.own("tagX", ["cook"], PSI.newKey()), b = await PSI.own("tagX", ["cook"], PSI.newKey()), c = await PSI.own("tagY", ["cook"], PSI.newKey());
  const va = a.vals[a.order.indexOf("cook")], vb = b.vals[b.order.indexOf("cook")];
  assert.notEqual(va, vb);
  assert.ok(!c.vals.includes(va));
});

test("waiting: no result until everyone has picked and every set has gone all the way round", async () => {
  const members = ["a", "b"], ka = PSI.newKey(), oa = await PSI.own("t", ["cook"], ka);
  const docs = { a: { own: oa.vals, fwd: {} } };
  const fin = await PSI.finals(members, docs);
  assert.equal(PSI.matches(members, "a", fin, oa.order), null);
  assert.equal(PSI.matches(["a"], "a", [oa.vals], oa.order), null, "alone in a space: nothing to match");
});

test("a tampered or stale link in the chain stops matching instead of giving a wrong answer", async () => {
  const r = await run("tag5", { a: ["cook"], b: ["cook"] });
  const bad = JSON.parse(JSON.stringify(r.docs));
  bad.b.fwd[0].v[0] = bad.b.fwd[0].v[1];                       // bob alters alice's set
  bad.b.fwd[0].from = "0".repeat(24);
  const fin = await PSI.finals(r.members, bad);
  assert.equal(fin[0], null);
  assert.equal(PSI.matches(r.members, "a", fin, r.st.a.order), null);
});

test("an oversized set (someone picking everything) is never forwarded", async () => {
  const members = ["a", "b"], kb = PSI.newKey();
  const big = Array.from({ length: 32 }, () => (5n).toString(16));
  const fwd = await PSI.forward(members, "b", { a: { own: big, fwd: {} }, b: { own: null, fwd: {} } }, kb, {});
  assert.deepEqual(fwd, {});
});

test("picks beyond the cap are dropped before blinding", async () => {
  const o = await PSI.own("t", ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"], PSI.newKey());
  assert.equal(o.vals.length, PSI.CAP);
  assert.equal(o.order.filter(Boolean).length, PSI.CAP);
});
