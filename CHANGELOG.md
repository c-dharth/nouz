# Changelog

## 0.11.0 — 2026-11-21

Added: Daily Forecast, the first tab in Intimacy → Insights.
- One word a day ("Today, you are MAGNETIC") with a line, the date and VOUZ / DAILY FORECAST, in large editorial type over a gradient tinted by the word.
- Four energies (Chemistry, Communication, Intimacy, Adventure) as dots and words, never numbers. An energy with too little evidence says so.
- Three short sections (Your connection, What to embrace, What to watch), each tagged Observed, Reflection or Suggestion.
- Today's move, which opens into three questions to ask each other, date ideas, a nearby search, and optional closeness ideas (off by default, own forecast only).
- A 10-second check-in (energy, how connected, what would feel good). A solo forecast can be updated once with it.
- One forecast per day, stored and never re-rolled. Words aren't repeated within 10 days; "Not quite" records a better word and steers future picks.
- Together mode, for two people who both opt in. It uses only what both agreed to share: check-ins and memories in a shared space. Both see the same forecast: it's seeded by the pair, and the first one made is sent encrypted to the other. Pulse shows each energy only if that person allows it.
- History calendar of past words, with a monthly line labelled as reflections, not a measure.
- Share cards (Minimal, Couple, Editorial) in Story 9:16 or Square 1:1, previewed before anything leaves VOUZ. Couple card initials and energy lines are off by default; cards never include check-ins or records.
- Claude can rewrite the three paragraphs from the word, the energies and the observed facts. Off by default. Anything that predicts, diagnoses, gets explicit or links out is discarded for the built-in library.
- Supabase migration 0007: private check-ins, opt-in sharing, one forecast per pair per day.

Fixed: the connection guide was sending blank idea names to Claude.

## 0.10.0 — 2026-11-19

Added:
- Connection guide, in Intimacy → Insights → Connection. An AI guide (Claude, through the platform) that gives a gentle read of the whole relationship: dates and memories, private ratings and moods, plans done, and intimacy patterns, with ideas to try next.
- Off until turned on. It receives totals and trends from the last 24 weeks, built on the device and viewable in full ("What the guide sees"). Never individual records, notes, titles, names, places, photos, tags or heart rate.
- Told never to treat more intimacy as better, never to set targets, never to present dates as a way to get more intimacy, and that it is not a therapist or doctor. Links are stripped from answers; only real ideas from VOUZ's list are offered.
- If a question suggests someone may not be safe, it shows the National Domestic Violence Hotline and 988.
- Conversations aren't saved and aren't shared with partners.

## 0.9.1 — 2026-11-19

Changed:
- Home and Feed are one tab. Home keeps the greeting, progress, quick actions, what's coming up and the private Intimacy row, with the feed (Explore and Friends) below. Notifications moved to the Home header; Friends and Saved sit on the feed heading.
- The "Recent" memories row left Home; they're in Our Story.
- Five tabs again: Home, Intimacy, Discover, Our Story, Profile.

## 0.9.0 — 2026-11-19

Discover now uses four connectors together (each called with the inputs its live tool declares, checked on 19 Nov 2026):
- Mapbox: places with coordinates, addresses, websites and opening hours; turns the typed area into a map location; walking and driving times between plan stops.
- Yelp: ratings, review counts, photos and price levels.
- AllTrails: trails with length, time, elevation gain and distance to the trailhead.
- AccuWeather: current conditions and official alerts. Rain ranks indoor ideas higher; alerts lower outdoor ones.
- The same place from Mapbox and Yelp is merged into one card with both sources named.
- Results mix more kinds of places by default; "within 2 miles" and open-now are checked wherever Mapbox gives a location and hours.
- Day plans skip places Mapbox says are closed at that stop's time.

## 0.8.1 — 2026-11-19

Fixed:
- Discover returned nothing with Yelp connected. Before a viewer has allowed Yelp, the platform won't describe Yelp's search, so VOUZ refused to call it, and the call is what asks for approval. VOUZ now uses Yelp's published input schema until the description is available.
- When Yelp fails, Discover now says why (for example, needs approval or reconnect), shows labelled demo places, and offers Try again.

## 0.8.0 — 2026-11-19

Added (browser-tested; Yelp tested against a stand-in using Yelp's real input schema and result shape):
- Discover now opens on For You, Nearby and Saved. Ideas, Plans, Mutual Match and the idea generator are still one tap away. The Feed is unchanged and separate.
- Real places from the Yelp connector, called with each viewer's own connection. Without it, clearly labelled made-up demo places.
- Ask VOUZ: plain-language requests ("within 2 miles", "romantic under $50", "tonight", "something we haven't tried", "by public transit").
- Ranking you can read: distance, interests, the request, budget, Yelp rating and rank, open now, time of day, your feedback, novelty. Claude may add a one-line note using only those facts.
- "Plan our Saturday" asks only for what's missing (the day), then builds a timed plan from real places. Each stop can be replaced; budget and distance can change; regenerate, save, share to a space, or add to calendar (.ics). Nothing is booked or paid.
- Each card: name, Yelp photo, address, distance, travel time, cost, hours, rating and why it fits. Estimates are marked; distance and hours say "not provided" or "not verified" when Yelp doesn't give them.
- Location: a typed neighborhood or city, or precise location only on tap, rounded to about 1 km and kept on the device.
- Planning together: share your taste (interest weights, price level, distance) with chosen connections, encrypted for each. Group results balance everyone and never show one person's preferences.
- The loop: after a planned date, Home asks how it went: private rating, mark done, then add photos, make a card, post. Points follow the existing rules; there are no merchant rewards.
- Controls: learning on/off, AI notes on/off, travel mode, reset personalization, delete recommendation history.
- Supabase migration 0006: saved places, feedback, history, shared taste (connections only), server-only provider cache.

## 0.7.0 — 2026-11-19

Added (browser-tested with four simulated users):
- Feed tab with Explore and Friends. The old Social page becomes Friends (people, requests, search, blocked) and My posts.
- Post types: memory card, photo (up to 4), video (up to 60 s, 10 MB), date, trip, milestone, recommendation, badge.
- Visibility on every post: Public, Friends, or Private (chosen friends). Friends and Private posts and their media are encrypted for their audience.
- Media upload: photos re-encoded (no EXIF/GPS); video location boxes and coordinates overwritten before upload. Stored in pieces, deleted with the post.
- Optional place tag, limited to a neighborhood or city; numbers and street words are refused.
- Likes (one per person), comments, saving (private), sharing (public or own posts), edit caption and place, delete, report, block.
- Explore ranking you can inspect: recency, engagement, your interests, detail, and a penalty for repeat authors. "Why this post?", a Latest view with no personalization, search, kind filters, Show more.
- Friends feed: newest first, with an empty state.
- Profiles: photo, bio, posts, add/accept/remove friend, block. Couple profiles: name, photo, bio, favorite things, achievements; live only when both approve the same version. Posts as the couple need the partner's approval.
- Blocking now works both ways: a block marker tells the blocked person's app to hide the blocker.
- In-app notifications: friend requests, likes, comments, couple and joint-post approvals, share requests.
- Moderation page for the page owner: open reports, remove a public post, dismiss.
- Supabase migration 0005: post kinds and fields, media index and storage policies, saved posts, couple profiles and approvals, notifications by trigger, Explore and Friends feed functions, moderators.

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
