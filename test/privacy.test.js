// 0.14 helpers exactly as they ship in web/index.html: QR codes, zip export, shared-session codes, pairing codes, calendar files, session types.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { inflateRawSync } from "node:zlib";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const cut = (a, b) => html.slice(html.indexOf(a), html.indexOf(b, html.indexOf(a)));
const te = new TextEncoder(), td = new TextDecoder();
const b64 = u => Buffer.from(u).toString("base64"), ub64 = s => new Uint8Array(Buffer.from(s, "base64"));
const esc = s => String(s);
const QR = new Function("te", "esc", cut("const QR=(()=>", "/* ============ passphrase") + "\nreturn QR;")(te, esc);
const Z = new Function("te", "td", cut("const CRC_T=", "/* ============ calendar file") + "\nreturn {crc32,zipMake,zipRead};")(te, td);
const cats = new Function(cut("const CATS=", "const legacySessions") + "\nreturn {CATS,CAT_ALL,convCat,catLabel,pCount};")();
const SC = new Function("te", "td", "b64", "ub64", "CAT_ALL", "convCat", "S", "uid", "save",
  cut("const SC_PRE=", "/* ============ zip") + "\nreturn {sessionCode,readSessionCode,addFromCode};");
const P = new Function("te", cut("const APP_URL=", "const pairState") + "\nreturn {pairNorm,pairFmt,pairNew,pairText,APP_URL};")(te);
const planIcs = new Function(cut("function planIcs", "/* ============ backup") + "\nreturn planIcs;")();

test("QR: sizes follow the version needed, finder patterns in three corners", () => {
  for (const [t, n] of [["hi", 21], ["x".repeat(60), 33], ["x".repeat(200), 57]]) {
    const m = QR.make(t); assert.equal(m.length, n);
    for (const [x, y] of [[0, 0], [n - 7, 0], [0, n - 7]]) {
      for (let i = 0; i < 7; i++) assert.ok(m[y][x + i] && m[y + 6][x + i] && m[y + i][x] && m[y + i][x + 6], "finder ring");
      assert.ok(m[y + 3][x + 3], "finder centre");
    }
    assert.ok(m[n - 8][8], "the dark module is set");
  }
  assert.throws(() => QR.make("x".repeat(400)));
});
test("QR: the SVG is self-contained with a white quiet zone", () => {
  const s = QR.svg("hello", "Invite");
  assert.match(s, /^<svg class="qr" viewBox="0 0 29 29"/); assert.ok(s.includes('aria-label="Invite"') && s.includes('fill="#fff"'));
});

test("zip: CRC-32 matches the standard check value", () => assert.equal(Z.crc32(te.encode("123456789")), 0xCBF43926));
test("zip: what we write, we read back byte for byte", async () => {
  const photo = new Uint8Array(5000).map((_, i) => (i * 37) & 255);
  const blob = Z.zipMake([{ name: "vouz-export.json", data: te.encode('{"app":"vouz"}') }, { name: "photos/p1.jpg", data: photo }]);
  const files = await Z.zipRead(await blob.arrayBuffer());
  assert.equal(td.decode(files["vouz-export.json"]), '{"app":"vouz"}');
  assert.deepEqual(files["photos/p1.jpg"], photo);
});
test("zip: also reads deflated archives (a zip re-saved by another tool)", async () => {
  const { deflateRawSync } = await import("node:zlib");
  const data = te.encode("same text ".repeat(50)), comp = deflateRawSync(data), name = te.encode("vouz-export.json");
  const loc = Buffer.alloc(30); loc.writeUInt32LE(0x04034b50, 0); loc.writeUInt16LE(8, 8); loc.writeUInt32LE(Z.crc32(data), 14); loc.writeUInt32LE(comp.length, 18); loc.writeUInt32LE(data.length, 22); loc.writeUInt16LE(name.length, 26);
  const cen = Buffer.alloc(46); cen.writeUInt32LE(0x02014b50, 0); cen.writeUInt16LE(8, 10); cen.writeUInt32LE(comp.length, 20); cen.writeUInt32LE(data.length, 24); cen.writeUInt16LE(name.length, 28); cen.writeUInt32LE(0, 42);
  const off = 30 + name.length + comp.length, end = Buffer.alloc(22); end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(1, 8); end.writeUInt16LE(1, 10); end.writeUInt32LE(46 + name.length, 12); end.writeUInt32LE(off, 16);
  const buf = Buffer.concat([loc, name, comp, cen, name, end]);
  const files = await Z.zipRead(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length));
  assert.equal(td.decode(files["vouz-export.json"]), "same text ".repeat(50));
});

test("session types: Solo and Partnered are kept, older values convert, labels are neutral", () => {
  const { convCat, catLabel, pCount, CATS } = cats;
  assert.deepEqual(convCat("solo"), { category: "solo", participants: 1 });
  assert.deepEqual(convCat("partnered"), { category: "partnered", participants: null });
  assert.deepEqual(convCat("duo"), { category: "couple", participants: 2 });
  assert.deepEqual(convCat("group", 6), { category: "poly", participants: 6 });
  assert.equal(catLabel({ category: "poly", participants: 4 }), "More than two · 4");
  assert.equal(catLabel({ category: "couple" }), "Two of us");
  assert.equal(catLabel({ category: "solo" }), "Solo");
  assert.equal(catLabel({ category: "partnered" }), "With a partner");
  assert.equal(pCount("solo"), 1); assert.equal(pCount("couple"), 2); assert.equal(pCount("poly", 99), 20);
  assert.ok(!Object.values(CATS).some(l => /couple|poly/i.test(l)));
});

test("session codes: round trip, only shareable fields, no duplicates, Solo can't be sent", () => {
  const S = { sessions: [] }; let n = 0;
  const m = SC(te, td, b64, ub64, cats.CAT_ALL, cats.convCat, S, () => "id" + (n++), () => {});
  const sess = { id: "s1", start: 1700000000000, durationSec: 1500, category: "poly", participants: 4, sharedNote: "hi", notes: "SECRET", title: "TITLE", mood: "Tender", satisfaction: 5 };
  const code = m.sessionCode(sess);
  assert.ok(code.startsWith("VOUZ-S1:") && /^[A-Za-z0-9:_-]+$/.test(code.replace("VOUZ-S1:", "")));
  const o = m.readSessionCode("Here you go: " + code + " ");
  assert.deepEqual(o, { v: 1, i: "s1", s: 1700000000000, d: 1500, c: "poly", p: 4, n: "hi" });
  assert.ok(!JSON.stringify(o).match(/SECRET|TITLE|Tender/));
  assert.equal(m.addFromCode(o), "ok"); assert.equal(m.addFromCode(o), "dup");
  assert.equal(S.sessions[0].participants, 4); assert.equal(S.sessions[0].notes, "");
  assert.equal(m.readSessionCode(m.sessionCode({ ...sess, category: "solo" })), null);
  assert.equal(m.readSessionCode("VOUZ-S1:not-json"), null);
  assert.equal(m.readSessionCode(m.sessionCode({ ...sess, durationSec: 999999 })), null);
});

test("pairing codes: 12 characters, no look-alikes, forgiving to type", () => {
  for (let i = 0; i < 50; i++) { const c = P.pairNew(); assert.match(c, /^[2-9A-HJKMNP-TV-Z]{12}$/); }
  assert.equal(P.pairNorm("k7qm-9tdx 2p4r"), "K7QM9TDX2P4R");
  assert.equal(P.pairFmt("K7QM9TDX2P4R"), "K7QM-9TDX-2P4R");
  assert.ok(P.pairText("K7QM9TDX2P4R").includes(P.APP_URL) && P.pairText("K7QM9TDX2P4R").includes("K7QM-9TDX-2P4R"));
});

test("calendar: a plan becomes one event with its title, place and a two-hour slot", () => {
  const t = new Date(2026, 11, 5, 19, 30).getTime();
  const ics = planIcs({ id: "p1", title: "Dinner, then a walk", location: "Pier 39; SF", date: t });
  assert.ok(ics.includes("DTSTART:20261205T193000") && ics.includes("DTEND:20261205T213000"));
  assert.ok(ics.includes("SUMMARY:Dinner\\, then a walk") && ics.includes("LOCATION:Pier 39\\; SF") && ics.includes("UID:p1@vouz"));
  assert.ok(ics.split("\r\n")[0] === "BEGIN:VCALENDAR" && ics.endsWith("END:VCALENDAR"));
});
