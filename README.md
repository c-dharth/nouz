# nouz (formerly VOUZ)

Relationship experiences, intimacy tracking and personal analytics for adults. "Less scrolling. More together."
Private by default. Shared only by choice. No scores.

Working with an AI assistant? Start with [AGENTS.md](AGENTS.md): it holds the project rules every tool should follow.

## What is in this repository

| Path | What it is | State |
|---|---|---|
| `web/index.html` | The working app (single file, no build step): Home (feed, plus Discover and Our Story), Sessions, Insights, Share, Profile | Working, browser-tested |
| `core/timer.js` | Session timer state machine over stored timestamps | Tested, not yet wired into the app |
| `core/streaks.js` | Weekly streaks, Monday to Sunday | Tested, not yet wired into the app |
| `core/storage.js` | Vault: migrations, backup, corruption recovery, export/import, optional encryption | Tested, not yet wired into the app |
| `core/sync.js`, `core/backend.js` | Offline queue, conflict handling, Supabase client | Tested against a stand-in server |
| `core/entitlements.js` | VOUZ Plus entitlement rules | Tested |
| `supabase/migrations/` | Database schema and row-level security | Tested on local Postgres, not deployed |
| `supabase/functions/` | Account deletion, purchase verification | Written, never run |
| `watch/` | Apple Watch app source and iPhone bridge | Written, never compiled |
| `e2e/run.py` | Browser tests for the app, including simulated users and connector stand-ins | 416 checks |

The Capacitor project (`ios/`, `android/`, `capacitor.config`) is **not** in this repository. See CHECKLIST.md.

## Running the tests

```
npm test            # 123 unit tests (incl. QR codes, zip export, session codes, astronomy against Meeus reference values, private matching, rewards, feed and discover helpers, run straight from web/index.html): timer, streaks, storage, sync, backend client, entitlements (Node 20+)
npm run test:db     # 208 policy tests on a throwaway local Postgres (needs initdb and psql)
npm run test:ui     # 317 browser checks (needs Python, Playwright and Chrome)
```

No packages are installed by any of these. There are no runtime dependencies.

## Configuration

Copy `.env.example` to `.env`. With the Supabase values blank the app is fully local and offline.
The service role key and store credentials belong only in Supabase function secrets, never in the app.

## Privacy rules the code enforces

- Sessions, notes and settings are readable only by their owner, in the database as well as in the app.
- Nothing is granted to signed-out visitors.
- A shared card is a whitelist. The database rejects a card carrying notes, mood, tags, heart rate, exact times or people.
- Social is off twice over: for the whole project, and per person. Both must be on.
- Plus can only be granted by the server after a store receipt is verified. The verification stubs refuse everything until credentials exist.
- Browser storage and the screen-lock passcode are not encryption. Only `sealed()` in `core/storage.js` encrypts, and on a phone its key must live in the Keychain or Keystore.

## How the app is organised

| Tab | What's there |
|---|---|
| Feed | Explore (public posts, ranked or latest, search, filters) and Friends (newest first); compose, notifications, saved, friends |
| Home | Greeting, quick actions, invitations, coming-up plans, an idea, recent memories, this week's intimacy count (private) |
| Intimacy | Track (timer, Couple/Poly, quick log), History (week ring, calendar, list, achievements), Insights |
| Discover | For You (Ask VOUZ, ranked real places, day plans), Nearby, Saved; Ideas with filters, AI Planner, private Mutual Match inside a shared space, Plans |
| Our Story | Timeline of memories, anniversary reminders, filter by shared space |
| Profile | Rewards and achievements, storage and sync, Connections, shared spaces, friends, public and couple profiles, moderation (owner), passcode, export, VOUZ Plus, delete |

Sessions are **Couple** (exactly 2) or **Poly** (3 to 20, with a counter). Confirmation status is Self-reported,
Pending confirmation or Mutually confirmed. Confirmation is voluntary and is never described as proof.

## Not included, by decision

- Solo and Partnered sessions. Existing ones are removed on upgrade after a one-time notice with a download option.

- VOUZ Pause (abstinence or celibacy tracking, reflection streaks).
- Automatic or nearby detection of other people.

## Rewards

Points (VP) are worked out from the records that exist, under keys that can only be awarded once, so nothing is
double-counted and deleting a record removes its points. Values and caps live in `RW.VP` and `RW.CAPS` in
`web/index.html` (and in the `vp_rules` table on the server). Intimacy earns at most once a week regardless of
frequency, duration or head count. Rewards are virtual only; partner rewards are gated off until a verified server
feed exists. In the web app the ledger runs on the device; `supabase/migrations/0004_rewards.sql` moves it to
database triggers so a client can't grant itself points.

## Shareable memory cards

Memory → Share as a card. Four templates (Minimal, Cinematic, Polaroid, Editorial), three shapes (1080×1920,
1080×1080, 1920×1080), five backgrounds, caption, up to three photos, date/place/branding toggles. The card is drawn
on a canvas and encoded straight to PNG or JPEG, so the file carries no camera or GPS data.

Share uses, in order: the native share plugin in the Capacitor app (untested), the browser share sheet with the
image file, then the platform save (which opens the iOS share sheet inside the Claude iPhone app). Memories in a
shared space can only be exported once everyone else in the space agrees; agreement can be withdrawn.

## Feed

Feed → Explore shows public posts from everyone who can open the app; Friends shows what friends shared with you,
newest first. Every post is Public, Friends or Private. Friends and Private posts are sealed with a fresh key that is
wrapped only for their audience, and their photos and video are encrypted with a key carried inside the sealed post.
Public posts and their media are readable by anyone who can open the app.

Explore's score is shown on each post: recency (40, halving every 3 days), engagement (up to 25, log of likes plus
twice the comments), your interests (15), detail (media 5, a real caption 3, a place 2), and −12 for each further post
by the same author. "Latest" skips all of it. The same formula runs server-side in `explore_feed()` (migration 0005).

Nothing is posted automatically. Intimacy records, session details, private notes, partners' names and locations are
never part of a post. Place tags are a neighborhood or city only.

**Scale.** In the web app, "public" means everyone the page is shared with, and on a personal plan only people
invited as editors can write. Media is stored in 180 KB pieces in the page's database. Real public use needs the
Supabase backend (migration 0005 plus a private Storage bucket), which isn't deployed.

## Discover

Discover combines four of the viewer's own connectors, called through the artifact's `mcp` capability with exactly the
inputs each live tool declares:

| Connector | Tools | What VOUZ uses |
|---|---|---|
| Mapbox | `category_search_tool`, `search_and_geocode_tool`, `directions_tool` | places, coordinates, addresses, websites, opening hours; area lookup; walking/driving times |
| Yelp | `yelp_search_local_businesses` | ratings, review counts, photos, price level |
| AllTrails | `find_trails_near_location` | trails: length, time, gain, distance to trailhead |
| AccuWeather | `widgets-search-claude`, `widgets-current-claude` | current conditions, official alerts |

A place found by both Mapbox and Yelp becomes one card. Anything a source doesn't give is labelled as not provided or
not verified, never filled in. Each person has to connect the connectors themselves and allow VOUZ to use them; without
any, Discover shows made-up demo places labelled on every card.

The ranking is in `scoreVenue()` and every factor is visible. Claude (the `sample` capability) only writes one-line notes
from the facts it's given. Recommendations never read intimacy records, notes or health data.
