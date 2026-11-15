// VOUZ watch timer. Same model as the phone (core/timer.js): elapsed time is derived from stored
// wall-clock segments, so the wrist going down, the app being suspended or the watch restarting cannot lose time.
// UNBUILT: written without Xcode. Compile and test on a device before relying on it.
import Foundation
import Combine

struct Segment: Codable, Equatable { var start: Double; var end: Double? }          // milliseconds since 1970, like the phone

struct ActiveSession: Codable, Equatable {
    var id: String
    var segments: [Segment]
    var category: String?
    var lastSeen: Double
    var isRunning: Bool { segments.last?.end == nil }
}

struct FinishedSession: Codable, Equatable, Identifiable {
    var id: String
    var start: Double
    var durationSec: Int
    var segments: [[Double]]
    var category: String?
    var source = "watch"
}

enum Recovery { case none, ok, stale(suggestedEnd: Double) }

@MainActor
final class SessionTimer: ObservableObject {
    static let maxMs: Double = 24 * 3600 * 1000
    static let staleAfterMs: Double = 6 * 3600 * 1000

    @Published private(set) var active: ActiveSession?
    @Published private(set) var outbox: [FinishedSession] = []       // finished, not yet confirmed by the phone
    @Published var recovery: Recovery = .none

    private let store: UserDefaults
    private let activeKey = "vouz.watch.active", outboxKey = "vouz.watch.outbox"
    var now: () -> Double = { Date().timeIntervalSince1970 * 1000 }

    init(store: UserDefaults = .standard) {
        self.store = store
        if let d = store.data(forKey: activeKey) { active = try? JSONDecoder().decode(ActiveSession.self, from: d) }
        if let d = store.data(forKey: outboxKey) { outbox = (try? JSONDecoder().decode([FinishedSession].self, from: d)) ?? [] }
        recover()
    }

    private func persist() {
        if let a = active, let d = try? JSONEncoder().encode(a) { store.set(d, forKey: activeKey) } else { store.removeObject(forKey: activeKey) }
        if let d = try? JSONEncoder().encode(outbox) { store.set(d, forKey: outboxKey) }
    }

    func start(category: String? = nil) {
        guard active == nil else { return }
        let t = now()
        active = ActiveSession(id: String(Int(t), radix: 36) + String(Int.random(in: 0..<1_679_616), radix: 36), segments: [Segment(start: t, end: nil)], category: category, lastSeen: t)
        persist()
    }

    func pause() {
        guard var a = active, a.isRunning else { return }
        let i = a.segments.count - 1
        a.segments[i].end = max(a.segments[i].start, now())
        a.lastSeen = now(); active = a; persist()
    }

    func resume() {
        guard var a = active, !a.isRunning, let lastEnd = a.segments.last?.end else { return }
        a.segments.append(Segment(start: max(now(), lastEnd), end: nil))
        a.lastSeen = now(); active = a; persist()
    }

    func setCategory(_ c: String?) { guard var a = active else { return }; a.category = c; active = a; persist() }

    /// Call when the scene becomes active and on a slow timer while visible.
    func heartbeat() { guard var a = active, now() > a.lastSeen else { return }; a.lastSeen = now(); active = a; persist() }

    func elapsedMs(at t: Double? = nil) -> Double {
        guard let a = active else { return 0 }
        let n = t ?? now()
        return min(Self.maxMs, a.segments.reduce(0) { $0 + max(0, ($1.end ?? n) - $1.start) })
    }

    /// A running session carries on across suspension. One that was left for hours is never saved silently: the person chooses.
    func recover() {
        guard let a = active else { recovery = .none; return }
        if a.isRunning, now() - a.lastSeen > Self.staleAfterMs || elapsedMs() >= Self.maxMs { recovery = .stale(suggestedEnd: a.lastSeen) } else { recovery = .ok }
    }

    enum StaleChoice { case trim, keep, discard }
    func resolveStale(_ c: StaleChoice) {
        guard var a = active else { return }
        switch c {
        case .discard: active = nil
        case .keep: a.lastSeen = now(); active = a
        case .trim:
            let i = a.segments.count - 1
            if a.segments[i].end == nil { a.segments[i].end = max(a.segments[i].start, a.lastSeen) }
            active = a
        }
        recovery = active == nil ? .none : .ok
        persist()
    }

    /// Stop. The finished session waits in the outbox until the phone confirms it has it.
    @discardableResult
    func finish() -> FinishedSession? {
        guard var a = active else { return nil }
        if a.isRunning { let i = a.segments.count - 1; a.segments[i].end = max(a.segments[i].start, now()) }
        var segs = a.segments.compactMap { s -> [Double]? in guard let e = s.end, e > s.start else { return nil }; return [s.start, e] }
        if segs.isEmpty { segs = [[a.segments[0].start, a.segments[0].start + 1000]] }
        let total = min(Self.maxMs, segs.reduce(0) { $0 + ($1[1] - $1[0]) })
        let done = FinishedSession(id: a.id, start: segs[0][0], durationSec: max(1, Int((total / 1000).rounded())), segments: segs, category: a.category)
        outbox.append(done); active = nil; recovery = .none; persist()
        return done
    }

    func discard() { active = nil; recovery = .none; persist() }
    func confirmDelivered(_ id: String) { outbox.removeAll { $0.id == id }; persist() }
}
