# nouz for iOS and Android

A Capacitor 8 shell around `web/index.html`. The web app stays the single source of truth: `npm run copy` puts it in `www/`, and Capacitor wraps it in a native app.

**State: source only.** Nothing here has been built or run on a phone. It was written in an environment without Xcode, the Android SDK or network access for `npm install`. The app's behaviour inside the shell is checked in Chromium by `e2e/mobile.py` (23 checks), which is not the same as a real device.

## Before you build

1. **Pick your app ID.** `capacitor.config.json` has `app.nouz.mobile` as a placeholder. Use a reverse domain you control (for example `com.yourdomain.nouz`). It can't be changed after the app is in a store.
2. **Tools.** iOS needs a Mac with Xcode 26 or later. Android needs Android Studio with SDK 35+. Both need Node 20+.

## Build

```
cd mobile
npm install
npm run icons            # icons and splash from resources/
npx cap add ios          # once; creates mobile/ios (Swift Package Manager)
npx cap add android      # once; creates mobile/android
npm run ios              # copies the web app, syncs, opens Xcode
npm run android          # same, opens Android Studio
```

Run `npm run sync` after every change to `web/index.html`. Commit `mobile/ios` and `mobile/android` once they exist.

In Xcode: set your Team under Signing & Capabilities, choose a device, press Run. In Android Studio: pick a device or emulator, press Run.

## What works in the phone app, and what doesn't yet

| | In the phone app |
|---|---|
| Sessions, Insights, Forecast, Our Story, plans, Mutual Match on one device | Works the same as the web app (stored on the phone) |
| Passphrase encryption, passcode, Quick hide, Discreet mode | Works the same |
| Android back button | Closes a sheet, then a page, then goes Home, then leaves. Never gets past Quick hide or the lock |
| Account sync, partner pairing, Social, shared spaces | **Not available.** These run on claude.ai's sign-in and database, which don't exist outside the artifact. They need the Supabase backend (migrations 0004–0008, not deployed) |
| Discover, Tonight, Planner, Connection guide | **Demo places only, or unavailable.** Yelp, Mapbox, AllTrails, AccuWeather and Claude are reached through claude.ai connectors. The phone app needs its own server to call them, with keys kept off the phone |
| Export (.zip), calendar files, share cards | **Untested.** Web downloads don't work in a native web view; they need `@capacitor/filesystem` and `@capacitor/share` |
| App switcher preview | Blurred by the web app on the way out; may still show content on some phones. A privacy-screen plugin would cover it |
| Apple Watch, HealthKit, push notifications, in-app purchases | Not built |

## Security settings in `capacitor.config.json`

- No `server.url`: the app ships its own files and never loads a website.
- `webContentsDebuggingEnabled: false` and `loggingBehavior: none` for release.
- `allowMixedContent: false`, `limitsNavigationsToAppBoundDomains: true`.

`node scripts/check.mjs` checks these, plus that no secret-looking key is in the web app.

## Before a store release (needs your decision)

- Privacy labels (App Store) and Data safety form (Play): with sync off, everything stays on the device.
- Age rating 17+ / Mature 18+, and an age gate beyond self-declaration where the law requires it.
- Store listing copy, screenshots, a privacy policy URL and a support URL.
