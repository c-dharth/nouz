# VOUZ

Relationship experiences, intimacy tracking and personal analytics for adults. "Less scrolling. More together."
Private by default. Shared only by choice. No scores.

## What is in this repository

| Path | What it is | State |
|---|---|---|
| `web/index.html` | The working app (single file, no build step): Home, Intimacy, Discover, Our Story, Profile | Working, browser-tested |
| `core/timer.js` | Session timer state machine over stored timestamps | Tested, not yet wired into the app |
| `core/streaks.js` | Weekly streaks, Monday to Sunday | Tested, not yet wired into the app |
| `core/storage.js` | Vault: migrations, backup, corruption recovery, export/import, optional encryption | Tested, not yet wired into the app |
| `core/sync.js`, `core/backend.js` | Offline queue, conflict handling, Supabase client | Tested against a stand-in server |
| `core/entitlements.js` | VOUZ Plus entitlement rules | Tested |
| `supabase/migrations/` | Database schema and row-level security | Tested on local Postgres, not deployed |
| `supabase/functions/` | Account deletion, purchase verification | Written, never run |
| `watch/` | Apple Watch app source and iPhone bridge | Written, never compiled |
| `e2e/run.py` | Browser tests for the app, including three simulated users | 147 checks |

The Capacitor project (`ios/`, `android/`, `capacitor.config`) is **not** in this repository. See CHECKLIST.md.

## Running the tests

```
npm test            # 61 unit tests: timer, streaks, storage, sync, backend client, entitlements (Node 20+)
npm run test:db     # 96 policy tests on a throwaway local Postgres (needs initdb and psql)
npm run test:ui     # 147 browser checks (needs Python, Playwright and Chrome)
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
| Home | Greeting, quick actions, invitations, coming-up plans, an idea, recent memories, this week's intimacy count (private) |
| Intimacy | Track (timer, Couple/Poly, quick log), History (week ring, calendar, list, achievements), Insights |
| Discover | Ideas with filters, Mutual Match inside a shared space, Plans |
| Our Story | Timeline of memories, anniversary reminders, filter by shared space |
| Profile | Storage and sync, Connections, shared spaces, social feed, passcode, export, VOUZ Plus, delete |

Sessions are **Couple** (exactly 2) or **Poly** (3 to 20, with a counter). Confirmation status is Self-reported,
Pending confirmation or Mutually confirmed. Confirmation is voluntary and is never described as proof.

## Not included, by decision

- Solo and Partnered sessions. Existing ones are removed on upgrade after a one-time notice with a download option.

- VOUZ Pause (abstinence or celibacy tracking, reflection streaks).
- Automatic or nearby detection of other people.
