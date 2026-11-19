// Feed helpers exactly as they ship in web/index.html: the video location scrubber and the place-tag guard.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const cut = (a, b) => html.slice(html.indexOf(a), html.indexOf(b, html.indexOf(a)));
const scrubVideo = new Function(cut("function scrubVideo", "async function videoMeta") + "\nreturn scrubVideo;")();
const LOC_BAD = new Function(cut("const LOC_BAD=", "\n") + "\nreturn LOC_BAD;")();

const box = (type, payload) => { const p = Buffer.from(payload, "latin1"), b = Buffer.alloc(8 + p.length); b.writeUInt32BE(8 + p.length); b.write(type, 4, "latin1"); p.copy(b, 8); return b; };
const str = (u) => Buffer.from(u).toString("latin1");

test("removes an ©xyz location box and its coordinates", () => {
  const u = new Uint8Array(Buffer.concat([box("ftyp", "isom0000"), box("©xyz", "\u0000\u0013\u0015Ç+37.7749-122.4194/"), box("free", "xx")]));
  const len = u.length, hits = scrubVideo(u);
  assert.ok(hits >= 1);
  assert.equal(u.length, len, "file length unchanged, so offsets stay valid");
  assert.ok(!str(u).includes("©xyz") && !str(u).includes("37.7749"));
  assert.ok(str(u).includes("ftyp"), "other boxes untouched");
});

test("removes a 3GPP loci box", () => {
  const u = new Uint8Array(Buffer.concat([box("moov", ""), box("loci", "\u0000\u0000\u0000\u0000home\u0000somewhere")]));
  scrubVideo(u);
  assert.ok(!str(u).includes("loci") && !str(u).includes("somewhere"));
});

test("removes stray ISO 6709 coordinates anywhere in the file", () => {
  const u = new Uint8Array(Buffer.from("....meta +51.5007-000.1246+012.000/....", "latin1"));
  scrubVideo(u);
  assert.ok(!str(u).includes("51.5007"));
});

test("leaves a clean file alone", () => {
  const u = new Uint8Array(Buffer.concat([box("ftyp", "isom0000"), box("mdat", "abcdefgh")])), before = str(u);
  assert.equal(scrubVideo(u), 0);
  assert.equal(str(u), before);
});

test("place tags allow neighborhoods and cities, not addresses", () => {
  for (const ok of ["Mission District", "Oakland", "Lake Tahoe", "Le Marais, Paris"]) assert.ok(!LOC_BAD.test(ok), ok);
  for (const bad of ["123 Main St", "Apt 4", "500 Market Street", "Ocean Ave", "37.77, -122.41"]) assert.ok(LOC_BAD.test(bad), bad);
});
