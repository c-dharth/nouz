// Watch screens: home, running timer, recovery prompt.
// Nothing here detects anything. A session starts and stops only when the person taps.
// UNBUILT: written without Xcode.
import SwiftUI
import WatchKit

private let coral = Color(red: 1.0, green: 0.36, blue: 0.53)
private func clock(_ ms: Double) -> String {
    let s = Int(ms / 1000)
    return String(format: "%02d:%02d:%02d", s / 3600, (s / 60) % 60, s % 60)
}
private func haptic(_ t: WKHapticType) { WKInterfaceDevice.current().play(t) }

struct RootView: View {
    @EnvironmentObject var timer: SessionTimer
    @EnvironmentObject var link: PhoneLink
    @Environment(\.scenePhase) private var phase

    var body: some View {
        Group {
            if case .stale(let end) = timer.recovery { RecoveryView(suggestedEnd: end) }
            else if timer.active != nil { TimerView() }
            else { HomeView() }
        }
        .onChange(of: phase) { p in
            if p == .active { timer.recover(); timer.heartbeat(); link.flush() }
            link.publishState()
        }
    }
}

struct HomeView: View {
    @EnvironmentObject var timer: SessionTimer
    @EnvironmentObject var link: PhoneLink
    @State private var category: String?
    private let cats = ["solo": "Solo", "duo": "Duo", "trio": "Trio", "group": "Group"]
    private let order = ["solo", "duo", "trio", "group"]

    var body: some View {
        ScrollView {
            VStack(spacing: 10) {
                Text("vouz.").font(.system(.title3, design: .serif)).italic()
                Button {
                    timer.start(category: category); haptic(.start); link.publishState()
                } label: { Label("Start", systemImage: "play.fill").frame(maxWidth: .infinity) }
                    .tint(coral).buttonStyle(.borderedProminent)
                    .accessibilityLabel("Start session")
                // Optional, same four choices as the phone.
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 6) {
                    ForEach(order, id: \.self) { c in
                        Button(cats[c] ?? c) { category = category == c ? nil : c; haptic(.click) }
                            .tint(category == c ? coral : .gray)
                            .accessibilityAddTraits(category == c ? .isSelected : [])
                    }
                }
                StatusRow()
            }.padding(.horizontal, 4)
        }
    }
}

struct TimerView: View {
    @EnvironmentObject var timer: SessionTimer
    @EnvironmentObject var link: PhoneLink
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let running = timer.active?.isRunning ?? false
        VStack(spacing: 8) {
            // The label is recomputed from stored timestamps each second; no counter is kept.
            TimelineView(.periodic(from: .now, by: 1)) { ctx in
                Text(clock(timer.elapsedMs(at: ctx.date.timeIntervalSince1970 * 1000)))
                    .font(.system(.title2, design: .rounded)).monospacedDigit()
                    .accessibilityLabel("Elapsed time")
            }
            Text(running ? "In session" : "Paused").font(.footnote).foregroundStyle(.secondary)
            HStack {
                Button {
                    if running { timer.pause(); haptic(.stop) } else { timer.resume(); haptic(.start) }
                    link.publishState()
                } label: { Image(systemName: running ? "pause.fill" : "play.fill") }
                    .accessibilityLabel(running ? "Pause" : "Resume")
                Button {
                    timer.finish(); haptic(.success); link.flush(); link.publishState()
                } label: { Image(systemName: "stop.fill") }
                    .tint(coral).accessibilityLabel("Finish and save")
            }
            Button("Discard", role: .destructive) { timer.discard(); haptic(.failure); link.publishState() }.font(.footnote)
        }
        .animation(reduceMotion ? nil : .default, value: running)
        .task { while !Task.isCancelled { timer.heartbeat(); try? await Task.sleep(nanoseconds: 30_000_000_000) } }
    }
}

struct RecoveryView: View {
    @EnvironmentObject var timer: SessionTimer
    let suggestedEnd: Double
    var body: some View {
        ScrollView {
            VStack(spacing: 8) {
                Text("A session was left running.").font(.headline)
                Text("Last seen " + Date(timeIntervalSince1970: suggestedEnd / 1000).formatted(date: .omitted, time: .shortened)).font(.footnote).foregroundStyle(.secondary)
                Button("End it there") { timer.resolveStale(.trim); timer.finish() }.tint(coral)
                Button("It's still going") { timer.resolveStale(.keep) }
                Button("Discard", role: .destructive) { timer.resolveStale(.discard) }
            }
        }
    }
}

struct StatusRow: View {
    @EnvironmentObject var timer: SessionTimer
    @EnvironmentObject var link: PhoneLink
    var body: some View {
        VStack(spacing: 2) {
            Label(link.status.rawValue, systemImage: link.status == .reachable ? "iphone" : "iphone.slash").font(.footnote).foregroundStyle(.secondary)
            if !timer.outbox.isEmpty { Text("\(timer.outbox.count) waiting to sync").font(.caption2).foregroundStyle(.secondary) }
        }.accessibilityElement(children: .combine)
    }
}
