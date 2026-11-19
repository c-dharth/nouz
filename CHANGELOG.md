# Changelog

## 0.6.0 — 2026-11-18

Added (browser-tested):
- Shareable memory cards: Minimal, Cinematic, Polaroid, Editorial; 9:16, 1:1, 16:9; five backgrounds; live preview of the exact image.
- Caption (or favorite moment), photo choice (up to 3), show/hide date, place and branding.
- Share sheet with the image file, save as PNG or JPEG, copy image; clear messages where a route isn't allowed.
- Exports carry no metadata; source photos with GPS are verified stripped.
- Consent for memories in a shared space: encrypted request, everyone else agrees, withdrawable; partners can't export yours without asking.
- Share buttons on memories and keepsake cards.

## 0.5.0 — 2026-11-18

Added (tested):
- Rewards: VOUZ Points with configurable values, daily and weekly caps, once-only award keys, points that follow your records.
- Ten collectible badges with artwork, earned / up next / locked, progress bars; intimacy achievements kept in a separate private collection.
- Twelve levels by points earned; spending never lowers a level.
- Weekly challenges (never intimacy, no streaks) that fit budget, interests, energy and time; completed by choosing a qualifying memory.
- Optional weekly experience goal; Together totals per shared space with no comparisons.
- Rewards shop: three themes, two badge frames, two card styles, milestone keepsake cards. No coupons or partner offers.
- History of every earning, uncounted entry and redemption. Celebration card with animation (reduced-motion aware).
- Switches for points and achievements, and for celebrations.
- Private Mutual Match: picks are blinded with a Diffie-Hellman set intersection over the RFC 3526 2048-bit group, padded to 8 and capped at 8.
- AI Planner in Discover using the platform's ask-Claude capability, with explicit controls over what is sent.
- Supabase migration 0004: trigger-written points ledger, caps, validated challenges, atomic redemption, partner-reward gating.

## 0.4.0 — 2026-11-18

Product: VOUZ becomes a relationship-experiences app. Tagline "Less scrolling. More together."

Added (browser-tested unless marked):
- Session modes Couple (2) and Poly (3–20, counter starting at 3) on Track, the save form, quick log, invites, Replay, Insights and sharing.
- Satisfaction rating (1–5, optional, private) and a shared note that travels only with confirmation invites.
- Verification statuses: Self-reported, Pending confirmation, Mutually confirmed. Invite limit follows the head count.
- Quick log: three taps after a session; duplicate guard.
- Timed vs estimated kept apart in Replay and Insights; Couple vs Poly comparison; satisfaction trend.
- Memories and plans: title, date, kind, place (typed), favorite moment, mood, private notes, shared note, privacy.
- Photos on memories: on this device only, re-encoded without location data, not synced or exported.
- Our Story timeline with anniversary reminders for milestones.
- Discover: 32 generic ideas with budget, time, distance, setting, energy and interest filters; save, schedule, complete.
- Shared spaces: create, invite connections, accept, decline, leave, remove, delete. Encrypted in the browser; key changes when anyone leaves.
- Mutual Match inside a space: private picks, only ideas every member picked are revealed.
- New palette (near black, charcoal, ivory, wine, burgundy, muted rose) and five tabs.
- Supabase migration 0003: Couple/Poly with constraints, satisfaction, shared notes, private experiences table (tested locally, not deployed).

Changed:
- Solo and Partnered sessions are removed on upgrade after a one-time notice offering a download. Duo, Trio and Group convert.
- "Social" switch renamed Connections; the feed moved to a page under Profile.
- Session cards can no longer be shared with Everyone (needs every participant's consent). Achievement cards still can.
- Plus proposal updated to $3.99 a month / $29.99 a year.
- Published as a new private artifact; the earlier one is public and could not be updated.

## 0.3.0 — 2026-11-14

Added (all with automated tests unless marked):
- `core/timer.js`: start, pause, resume, stop over stored timestamps; recovery after backgrounding, lock and process death; "left running" detection with trim, keep or discard; clock-rollback guard; 24 h cap; idempotent save; duplicate and overlap detection.
- `core/streaks.js`: Monday to Sunday weeks, current and longest streak, total active weeks, 12-week view, 4/8/12/26/52 milestones, run history, opt-in streak sharing. Demo data excluded.
- `core/storage.js`: `vouz.v1` kept; schema 2 migration; pending/main/backup write order; corruption quarantine and recovery; serialised updates; export, import, wipe; optional AES-256-GCM sealing.
- `core/sync.js`, `core/backend.js`: offline queue with back-off, newer-wins merge with tombstones, Supabase REST client.
- `core/entitlements.js`: Free and Plus rules, grace period, offline trust window, mock and sandbox purchases refused in production builds.
- `supabase/migrations/0001_vouz_core.sql`: profiles, settings, sessions, notes, achievements, entitlements; row-level security; `upsert_session`, `export_my_data`, `delete_my_data`.
- `supabase/migrations/0002_vouz_social.sql`: connections, per-connection permissions, blocks, posts with a whitelisted card, audiences, reactions, comments, reports; project-wide and personal off switches.
- `supabase/functions/`: `delete-account`, `verify-entitlement` (untested, undeployed).
- `watch/`: watchOS app source and iPhone bridge (uncompiled).
- `.env.example`, `.gitignore`, `package.json` test scripts.

Changed:
- The app moved from `index.html` to `web/index.html`. Its contents are unchanged in this release.
- Browser tests moved to `e2e/run.py`.

Not changed: the app's screens, storage key, saved data, published artifact.

## 0.2.x — 2026-11-14

- Add connections to a saved session by invite (accept or decline), sealed in storage.
- Category picker on the Track screen; Category first on the save form.
- Solo, Duo, Trio, Group categories; earlier Partnered entries kept as they are.
