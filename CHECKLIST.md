# VOUZ feature checklist

Legend: **Done** = working and tested here. **Logic only** = code and tests exist, not yet connected to the app's screens.
**Source only** = written, never run. **Not started**. **Blocked** = needs something this environment does not have.

## Blocker that affects most of the list

The Capacitor project was not attached, only the brief. This work is built on the web app from this project.
That copy has no weekly-streak screens, so it has diverged from the Capacitor copy described in the brief.
Wiring the new modules into screens is on hold until the Capacitor project is shared, to avoid two diverging apps.

## Milestones

| # | Milestone | State | Notes |
|---|---|---|---|
| 1 | Audit and baseline | Done for the web app | 107 browser checks pass; git baseline taken. Capacitor copy not seen |
| 2 | Timer and recovery | Logic only | 14 tests. The app's current timer already stores timestamps; the "left running" prompt and duplicate warning are not on screen yet |
| 3 | Weekly streaks | Logic only | 11 tests. No streak screens in this copy |
| 4 | Local persistence | Logic only | 16 tests. Native secure key storage is Blocked (device build) |
| 5 | Replay and Insights | Unchanged this round | Existing: timeline, pauses, comparisons, reflections, heatmap, time-of-day, weekday, filters. Missing: personal records card, streak history, yearly view |
| 6 | Backend and sync | Schema Done locally; client Logic only | 84 policy tests on local Postgres with a Supabase stand-in. Not deployed. Sign-in screens Not started |
| 7 | Social infrastructure | Schema Done locally | Off by default at two levels. The app still uses the artifact's own storage for Social |
| 8 | Subscriptions | Logic only + Source only | 7 tests. No purchase screen, no StoreKit or Play Billing code. Verification stubs refuse all receipts |
| 9 | Apple Watch | Source only | Never compiled |
| 10 | Mobile build | Blocked | No Capacitor packages (installs are off), no Android SDK, no Xcode. No APK, AAB or IPA was produced |

## Decisions needed from you

1. **Which codebase is the source of truth?** Share the Capacitor project, or confirm this web app is.
2. **Notes on the server:** store readable (simpler, enables server export) or encrypted on the device first (server never sees them, but a lost key means lost notes)?
3. **Encryption at rest on the phone:** turn on `sealed()` with a Keychain/Keystore key? It needs a secure-storage plugin choice.
4. **Social on Supabase:** the artifact version encrypts connections-only cards end to end; the Supabase schema uses server-side rules instead. Pick one model.
5. **Prices:** $3.99 monthly and $29.99 annual are recorded as proposals only.

## Needs Xcode or a device

- Compile the watch target and fix whatever the compiler finds.
- Test WatchConnectivity delivery and acknowledgement on a paired watch.
- Choose and verify a secure-storage plugin; confirm the key survives relaunch and is excluded from backups as intended.
- Verify the timer across lock, background and force-quit on a real phone.
- Safe areas, haptics, status bar, splash, icons.
- HealthKit permission flow, if heart rate is wanted.
- StoreKit 2 products, sandbox purchases, restore.

## Commands once Xcode is installed

Run from the Capacitor project root (the folder with `capacitor.config`), after copying `web/` into its web directory:

```
xcode-select --install
sudo xcodebuild -license accept
npm install
npx cap sync ios
npx cap open ios
```

Then in Xcode: pick a signing team, select a simulator or device, press Run. For the watch target, follow `watch/README.md`.

Android, once Android Studio is installed:

```
npx cap sync android
cd android && ./gradlew assembleDebug
```

Backend, only after you approve deployment:

```
supabase link --project-ref <your-ref>
supabase db push
supabase functions deploy delete-account verify-entitlement
```
