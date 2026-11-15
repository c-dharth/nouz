# Changelog

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
