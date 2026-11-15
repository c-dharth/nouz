// iPhone side of the watch link. Add to the iOS app target (ios/App/App) once the Xcode project is open.
// It receives finished sessions from the watch, hands them to the web layer, and acknowledges each one.
// UNBUILT: written without Xcode. The JS event name must match the listener in the web app.
import Foundation
import WatchConnectivity
import Capacitor

final class PhoneBridge: NSObject, WCSessionDelegate {
    static let shared = PhoneBridge()
    weak var bridge: CAPBridgeProtocol?
    private var pending: [String] = []                       // sessions that arrived before the web view was ready

    func start(bridge: CAPBridgeProtocol?) {
        self.bridge = bridge
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
        flush()
    }

    private func flush() {
        guard let bridge else { return }
        for json in pending { bridge.triggerWindowJSEvent(eventName: "vouzWatchSession", data: json) }
        pending.removeAll()
    }

    /// Called from JS (through a small Capacitor plugin method) after the session is saved in the vault.
    func acknowledge(id: String) {
        guard WCSession.default.activationState == .activated else { return }
        WCSession.default.transferUserInfo(["type": "ack", "id": id])
    }

    func session(_ session: WCSession, didReceiveUserInfo userInfo: [String: Any] = [:]) {
        guard userInfo["type"] as? String == "session", let json = userInfo["json"] as? String else { return }
        DispatchQueue.main.async { self.pending.append(json); self.flush() }
    }
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {}
    func sessionDidBecomeInactive(_ session: WCSession) {}
    func sessionDidDeactivate(_ session: WCSession) { WCSession.default.activate() }
}
