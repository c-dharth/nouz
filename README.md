# VOUZ

Private-first intimacy and activity tracking for adults. "Your other cardio."
Track privately. Celebrate personally. Share optionally.

## What is in this repository

| Path | What it is | State |
|---|---|---|
| `web/index.html` | The working app (single file, no build step) | Working, browser-tested |
| `core/timer.js` | Session timer state machine over stored timestamps | Tested, not yet wired into the app |
| `core/streaks.js` | Weekly streaks, Monday to Sunday | Tested, not yet wired into the app |
| `core/storage.js` | Vault: migrations, backup, corruption recovery, export/import, optional encryption | Tested, not yet wired into the app |
| `core/sync.js`, `core/backend.js` | Offline queue, conflict handling, Supabase client | Tested against a stand-in server |
| `core/entitlements.js` | VOUZ Plus entitlement rules | Tested |
| `supabase/migrations/` | Database schema and row-level security | Tested on local Postgres, not deployed |
| `supabase/functions/` | Account deletion, purchase verification | Written, never run |
| `watch/` | Apple Watch app source and iPhone bridge | Written, never compiled |
| `e2e/run.py` | Browser tests for the app | 107 checks |

The Capacitor project (`ios/`, `android/`, `capacitor.config`) is **not** in this repository. See CHECKLIST.md.

## Running the tests

```
npm test            # 61 unit tests: timer, streaks, storage, sync, backend client, entitlements (Node 20+)
npm run test:db     # 84 policy tests on a throwaway local Postgres (needs initdb and psql)
npm run test:ui     # 107 browser checks (needs Python, Playwright and Chrome)
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

## Not included, by decision

- VOUZ Pause (abstinence or celibacy tracking, reflection streaks).
- Automatic or nearby detection of other people.
