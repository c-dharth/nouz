# VOUZ for Apple Watch (source only)

**Status: not built, not compiled, not tested.** These files were written without Xcode or a watch.
Treat them as a starting point that needs a compile pass and device testing.

## What is here

| File | Purpose |
|---|---|
| `VouzWatch/VouzWatchApp.swift` | App entry point |
| `VouzWatch/SessionTimer.swift` | Timer model: start, pause, resume, finish, recovery. Stored timestamps, same segment format as the phone |
| `VouzWatch/Views.swift` | Home, running timer, "left running" prompt, connection status, haptics |
| `VouzWatch/PhoneLink.swift` | WatchConnectivity: queued delivery of finished sessions, acknowledgements, live state |
| `VouzWatch/HeartRate.swift` | Optional heart rate through HealthKit. Present but not wired in; off until reviewed |
| `PhoneBridge.swift` | iPhone side: receives sessions, passes them to the web layer, acknowledges |

## How sync works

1. Finishing on the watch puts the session in an outbox that survives restarts.
2. `transferUserInfo` queues it for the phone. Delivery happens when the phone is next in reach.
3. The phone saves it under the same id (saving twice updates, never duplicates) and sends an acknowledgement.
4. The watch removes it from the outbox only after that acknowledgement.

## What the watch does not do

- It does not detect activity. A session starts and stops only on a tap.
- It does not read or write the Health "sexual activity" record.
- It does not read heart rate unless the person turns that on and grants permission.

## Adding it in Xcode

1. Open `ios/App/App.xcworkspace`.
2. File > New > Target > watchOS > App. Name `VouzWatch`, interface SwiftUI, "Watch App for Existing iOS App".
3. Delete the generated Swift files and add the files in `VouzWatch/` to the watch target.
4. Add `PhoneBridge.swift` to the iOS app target and call `PhoneBridge.shared.start(bridge: self.bridge)` from the main view controller.
5. In the web app, listen for the `vouzWatchSession` window event, save through the vault, then call the acknowledge method.
6. Heart rate only: add the HealthKit capability to the watch target and `NSHealthShareUsageDescription` to its Info.plist.
7. Build to a paired watch. The simulator does not exercise WatchConnectivity delivery reliably.
