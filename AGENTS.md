# Instructions for AI coding assistants

This file is for any AI assistant working on VOUZ (Claude, ChatGPT/Codex, Gemini, Copilot, Cursor and others).
CLAUDE.md, GEMINI.md, .cursorrules and .github/copilot-instructions.md all point here. Keep this file as the single
source of truth: change the rules here, not in the pointer files.

## What VOUZ is

A private-first app for adult couples and partners: relationship experiences (memories, plans, ideas, a shared
story) plus private intimacy tracking. Tagline: "Less scrolling. More together." Users are 18+.

## Where things are

| Path | What it is |
|---|---|
| `web/index.html` | The whole app: one HTML file, vanilla JS, no build step. Tabs: Home, Feed, Intimacy, Discover, Our Story, Profile |
| `core/` | Tested logic modules (timer, streaks, storage, sync, backend client, entitlements), not yet wired into the app |
| `supabase/migrations/` | Postgres schema + row-level security, numbered `0001`…`0005`. Never edit an applied migration; add a new one |
| `supabase/tests/` | Policy tests run on a throwaway local Postgres |
| `test/` | Node unit tests; some extract code straight from `web/index.html` between marker comments |
| `e2e/run.py` | Playwright browser tests with a stand-in multi-user database |
| `mobile/` | Capacitor 8 shell for iOS/Android; copies `web/index.html` into `www/`. Source only, never built |
| `e2e/mobile.py` | The app as the phone shell runs it (no claude.ai, stand-in Capacitor) |
| `watch/` | Apple Watch source, never compiled |
| `CHECKLIST.md` | What's done, what isn't, known limits, open decisions. Update it when you change state |
| `CHANGELOG.md` | One entry per version |

How `web/index.html` works: state `S` is saved to localStorage (`vouz.v1`); `render()` rebuilds `#app` from view
functions (`vHome`, `vFeed`, …); buttons carry `data-act="name"`, handled by `A.name`; inputs use `data-bind`.
Shared data goes through `Soc` (collections under the page's database); private data through `Cloud.priv(...)`.
Encryption helpers are in `K` (WebCrypto).

## Run the tests before and after every change

```
npm test            # unit tests (Node 20+)
npm run test:db     # database policy tests (needs initdb/psql)
npm run test:ui     # browser tests (Python + Playwright + Chrome)
npm run test:mobile # phone-shell checks (config + Chromium with a stand-in Capacitor)
```

Never report a test as passing unless you ran it and saw it pass. Don't weaken a test to make it pass.

## Rules that are not negotiable

Privacy and safety
- Intimacy session records, participant identities and sensitive statistics are never published or shared automatically.
- Nothing is ever posted without the user tapping Post. Jointly owned content needs every affected person's permission first.
- Posts never contain intimacy records, session details, private notes, partners' names, exact locations or GPS metadata.
  Place tags are a neighborhood or city only. Photos are re-encoded; video location metadata is scrubbed.
- Friends and Private posts and their media stay encrypted for their audience. Blocked users can't see restricted content.
- Private by default. Connections/social are off by default.

Product
- Sessions are Couple (exactly 2) or Poly (3–20). Solo and Partnered modes were removed; don't bring them back.
- VOUZ Pause (abstinence/celibacy tracking) is permanently excluded.
- Never incentivize sexual frequency, duration, participant count or performance. Intimacy never drives a streak or challenge.
- Never pressure users toward intimate activity.
- Rewards are virtual only. No fictional coupons, discounts or partnerships presented as redeemable.
- No shame-based or "more is better" language in analytics.

Engineering honesty
- Never hardcode credentials or keys. Secrets live only in `.env` (git-ignored) or Supabase function secrets.
- Don't claim something is built, tested or working on a device unless it was. Mark it in CHECKLIST.md as
  Done / Logic only / Source only / Not started / Blocked.
- Don't fabricate native functionality (Capacitor, Apple Watch, HealthKit, purchases). Simulated purchases are never shown as real.
- Don't deploy, enable public access, or switch on external services (Supabase, app stores, analytics) without the owner's approval.
- Modify, don't rebuild: preserve existing features unless asked to remove them.

## Style

- Keep the app a single file with no runtime dependencies unless the owner decides otherwise.
- Accessible: real buttons, labels, 44px touch targets, `aria-pressed`/`aria-label`, reduced-motion support.
- Copy is short, plain and warm. No exclamation-mark hype.
- Commit messages say what changed and why. Update CHANGELOG.md and CHECKLIST.md with user-visible changes.
