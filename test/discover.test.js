// Discover helpers exactly as they ship in web/index.html: request parsing, Yelp input building and result parsing.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const code = html.slice(html.indexOf("const DGROUPS="), html.indexOf("/* ---------- what each person likes"));
const M = new Function("S", "ui", "render", "typing", code + "\nreturn {parseAsk,normVenue,Conn,findList,kindOf,demoVenues,hav};")({ disc: {} }, {}, () => {}, () => false);

// Yelp's published input schema for yelp_search_local_businesses.
const YELP = { type: "object", additionalProperties: false, properties: {
  is_open_now: { default: false, type: "boolean" },
  latitude: { anyOf: [{ maximum: 90, minimum: -90, type: "number" }, { type: "null" }] },
  limit: { default: 5, maximum: 8, minimum: 3, type: "integer" },
  location: { anyOf: [{ maxLength: 250, minLength: 1, type: "string" }, { type: "null" }] },
  longitude: { anyOf: [{ maximum: 180, minimum: -180, type: "number" }, { type: "null" }] },
  query: { anyOf: [{ maxLength: 250, minLength: 1, type: "string" }, { type: "null" }] } } };

test("plain-language requests become filters", () => {
  const a = M.parseAsk("What can we do within 2 miles?");
  assert.ok(Math.abs(a.km - 3.218) < 0.01);
  const b = M.parseAsk("Find something romantic under $50");
  assert.equal(b.budget, 50); assert.equal(b.mood, "romance"); assert.ok(b.kinds.length > 0);
  const c = M.parseAsk("We have three hours and $100");
  assert.equal(c.hours, 3); assert.equal(c.budget, 100);
  assert.ok(M.parseAsk("Plan a spontaneous date tonight").now);
  assert.ok(M.parseAsk("Suggest something we haven't tried before").novel);
  assert.ok(M.parseAsk("Find a nice place accessible by public transportation").transit);
  const d = M.parseAsk("Plan our Saturday"); assert.ok(d.plan); assert.equal(d.day, 6);
  assert.equal(M.parseAsk("Plan something").day, undefined);
});

test("Yelp input uses only Yelp's own fields, within its limits", async () => {
  M.Conn.schemas["Yelp|yelp_search_local_businesses"] = YELP;
  const inp = await M.Conn.input("Yelp", "yelp_search_local_businesses", { term: "coffee", label: "Mission District", limit: 12, radiusM: 3000, openNow: true });
  assert.deepEqual(inp, { is_open_now: true, limit: 8, location: "Mission District", query: "coffee" });
  const withCoords = await M.Conn.input("Yelp", "yelp_search_local_businesses", { term: "parks", lat: 37.76, lon: -122.42, limit: 1 });
  assert.equal(withCoords.latitude, 37.76); assert.equal(withCoords.limit, 3);
});

test("a tool that doesn't describe itself isn't guessed at", async () => {
  M.Conn.schemas["X|t"] = null;
  await assert.rejects(M.Conn.input("X", "t", { term: "a" }), (e) => e.code === "no_schema");
});

test("Yelp results are read as Yelp gives them, nothing added", () => {
  const p = { businesses: [{ id: "a-1", name: "A Place", rating: 4.5, review_count: 10, is_closed: false, categories: [{ alias: "coffee" }],
    url: "https://www.yelp.com/biz/a-1", image_url: "https://s3-media0.fl.yelpcdn.com/x.jpg", location: { address1: "1 Main St\nTown, CA 94110" }, price: "$$", distance_meters: 0.2 }], status: "ok" };
  const L = M.findList(p); assert.equal(L.length, 1);
  const v = M.normVenue(L[0], "Yelp", 1);
  assert.equal(v.addr, "1 Main St, Town, CA 94110");
  assert.equal(v.kind, "coffee"); assert.equal(v.price, 2); assert.equal(v.rating, 4.5);
  assert.equal(v.distKm, null, "an implausible distance isn't shown");
  assert.equal(v.openNow, null); assert.equal(v.hoursText, null, "no hours claimed when Yelp gives none");
  assert.equal(v.lat, null);
  assert.equal(M.normVenue({ name: "x", url: "javascript:alert(1)", image_url: "http://insecure" }, "Yelp", 1).url, null);
});

test("demo places are labelled and fictional", () => {
  const d = M.demoVenues(null);
  assert.ok(d.every((v) => v.demo && v.src === "Demo" && /not a real place/.test(v.addr)));
});
