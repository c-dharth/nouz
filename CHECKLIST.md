# VOUZ feature checklist

**Done** = working and browser-tested. **Logic only** = code and tests, not on screen. **Source only** = written, never run.
**Not started**. **Blocked** = needs something this environment doesn't have.

Codebase: the single-file web app in `web/` (your choice, 18 Nov). Accounts: the artifact's built-in sign-in and database.

## Phase 1 — MVP

| # | Feature | State | Notes |
|---|---|---|---|
| 1 | Authentication | Done (platform) | Signed-in Claude account via the artifact. Not Supabase Auth yet |
| 2 | User profiles | Done | Handle, private/discoverable, connection codes |
| 3 | Couple and Poly selection | Done | Couple = 2; Poly 3–20 with counter; Solo/Partnered removed on upgrade |
| 4 | Session logging | Done | Timer, quick log, manual, edit, delete, satisfaction, private and shared notes |
| 5 | Participant confirmation | Done | Self-reported / Pending / Mutually confirmed; decline and step out |
| 6 | Session history | Done | Intimacy → History |
| 7 | Basic analytics | Done | Week/month/year/custom, heatmap, time of day, weekday, mood, satisfaction, Couple vs Poly, timed vs estimated |
| 8 | Relationship spaces | Done | Encrypted; owner invites connections; join, leave, remove, delete |
| 9 | Experience tracking | Done | Memories and plans; photos device-only |
| 10 | Mutual Match | Done | Per space; reveals only ideas every member picked |
| 11 | Privacy controls | Done | Private by default, Connections off by default, passcode, export, delete |

## Phase 2 and 3 — backlog

| Feature | State |
|---|---|
| AI experience planner | Done. Discover → Planner. Sends only the request, budget, time, a typed area and (optional) memory titles |
| Personalized recommendations | Done in the web app: Discover For You / Nearby / Saved with Yelp, Ask VOUZ day plans, learning from saves, plans, ratings and feedback. Server tables in migration 0006, tested locally |
| Monthly and yearly recaps | Not started |
| Smart reminders, push notifications | Not started; web page can't send push here |
| Shared wishlists | Not started (plans in a space cover part of it) |
| Photo sync between partners | Partly: photos and video posted to the feed are shared, encrypted for Friends/Private. Memory photos themselves are still device-only |
| Rewards, badges, levels, challenges, shop | Done (device); server ledger in migration 0004, tested locally |
| Weekly streaks on screen | Logic only (`core/streaks.js`); intimacy is deliberately never part of a streak |
| Apple Watch, HealthKit | Source only (`watch/`), never compiled |
| Subscriptions | Logic only (`core/entitlements.js`); no purchase screen |
| Supabase as the backend | Schema and policies tested locally (167 checks); not deployed; app not switched over |
| iOS/Android builds | Blocked: no Capacitor packages, Android SDK or Xcode here |

| Social feed: Explore & Friends | Done in the web app: posts with media, visibility, likes, comments, saves, share, edit, report, block, profiles, couple profiles, notifications, moderation. Server version in migration 0005, tested locally, not deployed |
| Shareable memory cards | Done in the web app. Native share plugin path written, untested; Instagram "Share to Stories" direct button needs the native app and a Meta app ID |

## Known limits

- **Card sharing on real devices:** not tested on a phone. In the web app, share and copy depend on what the browser allows inside the artifact; where blocked, the app saves instead or says it isn't available. A direct "Instagram Stories" button needs the native iOS app (it uses a Meta app ID and Instagram's pasteboard API), so for now Instagram is reached through the share sheet.
- **Card consent** is enforced in the app; someone could still screenshot a memory they can see. Once a card has been shared, withdrawing agreement can't recall it.

- **Mutual Match privacy:** picks are blinded with a private set intersection, so no one (members, storage or VOUZ) can read them. With three or more people, a member who inspected the data could tell which of their own picks each other person shares, not just the full match. Matching completes as each member opens the app.
- **Rewards in the web app** are computed on the device, so someone editing their own browser storage could give themselves points; that only affects their own virtual rewards. The Supabase migration moves awarding to the database.
- **Intimacy points** are capped at once a week so frequency never earns more. The server version doesn't yet add the "confirmed" bonus, because confirmations don't live on the server yet.
- **Leaving a space:** the space gets a new key, but someone who left may have kept copies of what they saw.
- **Feed scale in the web app:** "Public" is everyone the page is shared with, not the internet. On a personal plan only people invited as editors can post; viewers can read. Storage is the page's database (25,000 documents), so heavy video use will fill it. Supabase is the path to real scale.
- **Feed media** is encrypted for Friends and Private posts; someone who can see a post can still screenshot it. Removing a friend stops future access; it can't recall what they already saw.
- **Blocking** in the web app hides content in both apps; it can't stop someone determined from reading public posts, which anyone with access can read. The Supabase version enforces blocks in the database.
- **Video** location scrubbing covers the standard boxes (©xyz, loci) and ISO 6709 coordinate strings; it is checked with test files, not with every phone's format. Videos aren't re-encoded.
- **Moderation** in the web app is for the page owner only; there's no appeals flow or automated screening.
- **Notifications** are in-app only. No push.
- **Connectors in VOUZ** (Mapbox, Yelp, AllTrails, AccuWeather) are tested against stand-ins built from each tool's real inputs and real responses, not yet with live accounts inside the artifact. Each person must connect them and allow VOUZ when asked.
- **Places only Yelp finds** have no map location or hours, so they show "not provided" for distance and "not verified" for hours. Mapbox's hours are used where it has them.
- **Events** (concerts, shows, markets) aren't covered: none of these connectors lists events. Planned: Ticketmaster and a Claude web-search agent once there's a funded backend.
- **Public transit** times are estimates; Mapbox gives walking and driving only.
- **Precise location** in the artifact depends on the browser allowing it; typing an area always works.
- **Merchant rewards:** none. VOUZ has no merchant partners and doesn't reward claimed visits.
- **Photos** are on one device only. Clearing browser data deletes them.
- **Poly matching** requires every member to pick before anything is revealed.
- Confirmation invites aren't updated if the session is edited after sending.
- Not tested: real signed-in accounts (multi-user checks use a stand-in database), real phones, screen readers.

## Decisions needed

1. Point values and caps (RW.VP, RW.CAPS) are first guesses: adjust after real use.
2. Supabase: when to deploy, and whether notes are encrypted on the device first.
3. Explore ranking weights (recency 40, engagement 25, interests 15, detail 10, repeat author −12) are first guesses.
4. Who moderates, and the community rules they enforce, before any real public launch.
5. When to fund the backend for events (Ticketmaster key, Claude API with web search).

## Commands once Xcode is installed

From the Capacitor project root, after copying `web/` into its web directory:

```
npm install
npx cap sync ios
npx cap open ios
```

Android, once Android Studio is installed: `npx cap sync android && cd android && ./gradlew assembleDebug`.
Backend, only after you approve: `supabase link --project-ref <ref> && supabase db push`.
