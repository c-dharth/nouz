// Checks the shell's config without Capacitor installed: what this repo can verify without a Mac.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
const here = dirname(fileURLToPath(import.meta.url));
const cfg = JSON.parse(readFileSync(join(here, "..", "capacitor.config.json"), "utf8"));
const html = readFileSync(join(here, "..", "..", "web", "index.html"), "utf8");
const fails = [];
const need = (ok, msg) => { if (!ok) fails.push(msg); };
need(/^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$/.test(cfg.appId), "appId must be reverse-DNS, lowercase");
need(cfg.webDir === "www", "webDir must be www (copy-web.mjs writes there)");
need(!cfg.server || !cfg.server.url, "server.url must not be set: the app ships its own files, it doesn't load a website");
need(cfg.android && cfg.android.webContentsDebuggingEnabled === false, "release builds must not allow web debugging");
need(cfg.android && cfg.android.allowMixedContent === false, "no mixed content");
need(html.includes("viewport-fit=cover"), "web app needs viewport-fit=cover for the notch and home bar");
need(html.includes("const Native="), "web app is missing the Native shell hooks");
need(!/sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}/.test(html), "something that looks like a secret key is in web/index.html");
if (fails.length) { console.error(fails.map(f => "FAIL " + f).join("\n")); process.exit(1); }
console.log("mobile shell config: all checks passed");
