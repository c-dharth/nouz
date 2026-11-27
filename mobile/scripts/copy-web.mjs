// Copies the one-file app into www/ for Capacitor. The web app stays the single source of truth.
import { mkdirSync, copyFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "web", "index.html");
const out = join(here, "..", "www");
if (!existsSync(src)) { console.error("Missing " + src); process.exit(1); }
mkdirSync(out, { recursive: true });
copyFileSync(src, join(out, "index.html"));
console.log("Copied web/index.html to mobile/www/index.html");
