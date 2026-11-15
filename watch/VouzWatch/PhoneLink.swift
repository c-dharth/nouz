// Watch <-> iPhone link over WatchConnectivity.
// Finished sessions use transferUserInfo: the system queues them and delivers when the phone is next reachable,
// even if neither app is open. The same session id is used on both sides, so a repeat delivery cannot duplicate.
// UNBUILT: written without Xcode.
import Foundation
import WatchConnectivity

@MainActor
final class PhoneLink: NSObject, ObservableObject, WCSessionDelegate {
    enum Status: String { case unsupported = "Not available", inactive = "Connecting", notReachable = "iPhone not in reach", reachable = "Connected" }
    @Published private(set) var status: Status = .inactive
    @Published private(set) var lastSyncedAt: Date?

    private weak var timer: SessionTimer?
    private var session: WCSession? { WCSession.isSupported() ? WCSession.default : nil }

    func attach(_ timer: SessionTimer) {
        self.timer = timer
        guard let s = session else { status = .unsupported; return }
        s.delegate = self
        s.activate()
    }

    private func refresh() {
        guard let s = session else { status = .unsupported; return }
        status = s.activationState != .activated ? .inactive : (s.isReachable ? .reachable : .notReachable)
    }

    /// Send everything still waiting. Safe to call often.
    func flush() {
        guard let s = session, s.activationState == .activated, let timer else { return }
        let alreadyQueued = Set(s.outstandingUserInfoTransfers.compactMap { $0.userInfo["id"] as? String })
        for f in timer.outbox where !alreadyQueued.contains(f.id) {
            guard let d = try? JSONEncoder().encode(f), let json = String(data: d, encoding: .utf8) else { continue }
            s.transferUserInfo(["type": "session", "id": f.id, "json": json])
        }
    }

    /// Tell the phone a session is in progress, so it can show it. Latest state only; not a history.
    func publishState() {
        guard let s = session, s.activationState == .activated, let timer else { return }
        var ctx: [String: Any] = ["type": "state", "running": timer.active?.isRunning ?? false, "active": timer.active != nil]
        if let a = timer.active, let d = try? JSONEncoder().encode(a), let j = String(data: d, encoding: .utf8) { ctx["json"] = j }
        try? s.updateApplicationContext(ctx)
    }

    // MARK: WCSessionDelegate
    nonisolated func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        Task { @MainActor in self.refresh(); self.flush() }
    }
    nonisolated func sessionReachabilityDidChange(_ session: WCSession) {
        Task { @MainActor in self.refresh(); self.flush() }
    }
    /// The phone acknowledges each session it has saved: ["type": "ack", "id": "..."].
    nonisolated func session(_ session: WCSession, didReceiveUserInfo userInfo: [String: Any] = [:]) {
        guard userInfo["type"] as? String == "ack", let id = userInfo["id"] as? String else { return }
        Task { @MainActor in self.timer?.confirmDelivered(id); self.lastSyncedAt = Date() }
    }
}
