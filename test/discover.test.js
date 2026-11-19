// Discover helpers exactly as they ship in web/index.html: request parsing and reading Mapbox, Yelp and AllTrails answers.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const code = html.slice(html.indexOf("const DGROUPS="), html.indexOf("/* ---------- what each person likes"));
const M = new Function("S", "ui", "render", "typing", code + "\nreturn {parseAsk,fromMapbox,fromYelp,fromTrail,mergeVenues,hoursAt,parseLoose,Conn,kindOf,demoVenues,hav};")({ disc: {} }, {}, () => {}, () => false);

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

// Shapes below are trimmed from real responses on 19 Nov 2026.
const MB = { type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Point", coordinates: [-122.41635482, 37.76129566] },
  properties: { name: "Hedge Coffee", mapbox_id: "abc", full_address: "434 Shotwell St, San Francisco, California 94110, United States",
    coordinates: { longitude: -122.41635482, latitude: 37.76129566 }, poi_category: ["café", "coffee", "coffee shop"], poi_category_ids: ["cafe", "coffee"],
    metadata: { website: "http://hedge.coffee/", open_hours: { periods: [1, 2, 3, 4, 5].map((d) => ({ open: { day: d, time: "0700" }, close: { day: d, time: "1600" } })) } }, distance: 207 } }] };
const YELP = { businesses: [{ id: "hedge-coffee-san-francisco-3", name: "Hedge Coffee", rating: 4.4974, review_count: 193, is_closed: false, categories: [{ alias: "coffee" }],
  url: "https://www.yelp.com/biz/hedge-coffee-san-francisco-3", image_url: "https://s3-media0.fl.yelpcdn.com/bphoto/x/o.jpg",
  location: { address1: "434 Shotwell St\nSan Francisco, CA 94110" }, price: "$$", distance_meters: 0.2 }], status: "ok", error: null };
const TRAIL = { id: 10239528, name: "Glen Canyon Park Loop", alltrails_web_url: "https://www.alltrails.com/trail/us/california/glen-canyon-park-trail",
  profile_photo_url: "https://www.alltrails.com/api/alltrails/trails/10239528/profile_photo?size=medium", avg_rating: 4.7, duration_minutes: 52,
  elevation_gain_feet: 314, length_miles: 1.9, location_label: "Glen Canyon Park, California", trail_head_distance_meters: 2773, difficulty: "Moderate", route_type: "Loop" };

test("Mapbox places keep coordinates, address, website and hours", () => {
  const v = M.fromMapbox(MB.features[0], 1);
  assert.equal(v.kind, "coffee"); assert.equal(v.lat, 37.76129566); assert.equal(v.site, "https://hedge.coffee/");
  assert.equal(v.addr, "434 Shotwell St, San Francisco, California 94110");
  const wed9 = new Date(2026, 10, 18, 9, 0), wed17 = new Date(2026, 10, 18, 17, 0), sun = new Date(2026, 10, 22, 10, 0);
  assert.equal(M.hoursAt(v.hours, wed9), true); assert.equal(M.hoursAt(v.hours, wed17), false); assert.equal(M.hoursAt(v.hours, sun), false);
  assert.equal(M.hoursAt(null, wed9), null, "no hours means unknown, not closed");
});

test("Yelp results are read as Yelp gives them, nothing added", () => {
  const v = M.fromYelp(YELP.businesses[0], 1);
  assert.equal(v.addr, "434 Shotwell St, San Francisco, CA 94110"); assert.equal(v.price, 2); assert.equal(v.rating, 4.4974);
  assert.equal(v.distKm, null, "an implausible distance isn't shown"); assert.equal(v.hours, null); assert.equal(v.lat, null);
  assert.equal(M.fromYelp({ ...YELP.businesses[0], is_closed: true }, 1), null, "permanently closed places are dropped");
  assert.equal(M.fromYelp({ name: "x", url: "javascript:alert(1)", image_url: "http://insecure" }, 1).url, null);
});

test("the same place from Mapbox and Yelp becomes one card with both sources' facts", () => {
  const [m] = M.mergeVenues([M.fromYelp(YELP.businesses[0], 1), M.fromMapbox(MB.features[0], 1)]);
  assert.deepEqual(m.srcs, ["Mapbox", "Yelp"]);
  assert.equal(m.lat, 37.76129566); assert.ok(m.hours); assert.equal(m.rating, 4.4974); assert.equal(m.price, 2);
  assert.ok(m.yelpUrl && m.site && m.photos.length === 1);
  const two = M.mergeVenues([M.fromYelp({ ...YELP.businesses[0], name: "Ritual Coffee Roasters" }, 1), M.fromMapbox(MB.features[0], 1)]);
  assert.equal(two.length, 2, "different places stay separate");
});

test("AllTrails trails carry length, time, gain and distance to the trailhead", () => {
  const v = M.fromTrail(TRAIL, 1);
  assert.equal(v.kind, "trail"); assert.equal(v.trail.miles, 1.9); assert.equal(v.trail.gainFt, 314); assert.equal(v.distKm, 2.773); assert.ok(v.free);
});

test("connector text with a note after the JSON still parses; plain text stays text", () => {
  const dir = JSON.stringify({ routes: [{ duration: 481, distance: 673 }] }, null, 2) + '\n\nIf the user wants to see this on a map, pass this ref unchanged to render_map_tool:\n   render_map_tool({ "payload_refs": ["mapbox://x"] })';
  assert.equal(M.parseLoose(dir).routes[0].duration, 481);
  const geo = '1. Mission District\n   Coordinates: 37.757046, -122.41892\n\nrender_map_tool({ "payload_refs": ["x"] })';
  assert.equal(typeof M.parseLoose(geo), "string", "text that doesn't start with JSON isn't mined for a stray object");
});

test("demo places are labelled and fictional", () => {
  const d = M.demoVenues(null);
  assert.ok(d.every((v) => v.demo && v.src === "Demo" && /not a real place/.test(v.addr)));
});
