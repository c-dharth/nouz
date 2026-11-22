// Astronomy behind VOUZ's astrology, exactly as it ships in web/index.html, checked against published reference values.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../web/index.html", import.meta.url), "utf8");
const A = new Function(html.slice(html.indexOf("/* ASTRO-START"), html.indexOf("/* ASTRO-END */")) + "\nreturn Astro;")();
const near = (a, b, tol) => assert.ok(Math.abs(((a - b + 540) % 360) - 180) <= tol, `${a} vs ${b}`);

test("Sun: Meeus Example 25.a (1992 Oct 13, 0h TD) apparent longitude 199.90895°", () => near(A.sunLon(2448908.5), 199.90895, 0.01));
test("Moon: Meeus Example 47.a (1992 Apr 12, 0h TD) apparent longitude 133.162655°", () => near(A.moonLon(2448724.5), 133.162655, 0.05));
test("Venus: Meeus Example 33.a (1992 Dec 20, 0h TD) apparent longitude 313.08102°", () => near(A.planetLon("venus", 2448976.5), 313.08102, 0.05));

test("Ascendant is the ecliptic point on the eastern horizon", () => {
  const R = Math.PI / 180;
  for (const [ms, lat, lon] of [[Date.UTC(1990, 0, 3, 0, 17), -33.9, 151.2], [Date.UTC(2004, 6, 10, 12, 0), 51.5, -0.1], [Date.UTC(2026, 10, 21, 22, 5), 37.77, -122.4], [Date.UTC(1975, 3, 1, 6, 0), 64.1, -21.9]]) {
    const asc = A.ascendant(ms, lat, lon), JD = A.jd(ms), T = (JD - 2451545) / 36525, eps = 23.4392911 - 0.0130042 * T;
    const ra = Math.atan2(Math.sin(asc * R) * Math.cos(eps * R), Math.cos(asc * R)) / R, dec = Math.asin(Math.sin(eps * R) * Math.sin(asc * R)) / R;
    const gmst = (280.46061837 + 360.98564736629 * (JD - 2451545)) % 360, H = ((gmst + lon - ra) % 360 + 540) % 360 - 180;
    const alt = Math.asin(Math.sin(lat * R) * Math.sin(dec * R) + Math.cos(lat * R) * Math.cos(dec * R) * Math.cos(H * R)) / R;
    assert.ok(Math.abs(alt) < 0.01, "on the horizon"); assert.ok(H < 0, "rising, in the east");
  }
});

test("Sun signs at the edges of the year and at cusps", () => {
  const sun = (d) => A.chart({ dob: d, tz: "UTC", time: "12:00" }).sun.sign;
  assert.equal(sun("1995-11-08"), "Scorpio"); assert.equal(sun("2000-01-01"), "Capricorn"); assert.equal(sun("2001-07-04"), "Cancer");
  assert.equal(sun("2026-11-21"), "Scorpio"); assert.equal(sun("2026-11-23"), "Sagittarius");
});

test("without a birth time, a body that changes sign that day is reported as either, never guessed", () => {
  const c = A.chart({ dob: "1995-11-08", tz: "America/Los_Angeles", unknownTime: true });
  assert.equal(c.moon.sign, null); assert.deepEqual(c.moon.either, ["Taurus", "Gemini"]);
  assert.equal(c.sun.sign, "Scorpio"); assert.equal(c.rising, undefined);
  const k = A.chart({ dob: "1995-11-08", tz: "America/Los_Angeles", time: "14:30", place: { lat: 37.77, lon: -122.42 } });
  assert.equal(k.moon.sign, "Gemini"); assert.ok(A.SIGNS.includes(k.rising.sign));
});

test("Mercury retrograde matches known periods", () => {
  for (const [d, r] of [["2024-04-10", true], ["2024-05-10", false], ["2025-03-25", true], ["2025-04-20", false], ["2026-11-01", true], ["2026-11-21", false]])
    assert.equal(A.sky(d, "UTC").mercuryRetro, r, d);
});

test("time zones follow the place's own daylight-saving history", () => {
  assert.equal(A.tzOffset("America/Los_Angeles", Date.UTC(1995, 6, 1)), -420);
  assert.equal(A.tzOffset("America/Los_Angeles", Date.UTC(1995, 11, 1)), -480);
  assert.equal(A.localToUTC(1995, 11, 8, 14, 30, "America/Los_Angeles"), Date.UTC(1995, 10, 8, 22, 30));
});

test("age counts whole years, including leap-day birthdays", () => {
  assert.equal(A.age("2008-11-22", "2026-11-21"), 17); assert.equal(A.age("2008-11-21", "2026-11-21"), 18);
  assert.equal(A.age("2008-02-29", "2026-02-28"), 17); assert.equal(A.age("2008-02-29", "2026-03-01"), 18);
});
