// Optional heart rate. Off unless the person turns it on and grants HealthKit read access for heart rate.
// VOUZ reads heart rate only while a session the person started is running, shows it back to them, and
// writes nothing to Health. It does not use, read or write the Health "sexual activity" record.
// UNBUILT and NOT WIRED INTO THE UI. Needs: the HealthKit capability, NSHealthShareUsageDescription,
// App Review notes explaining the use, and testing on a real watch. Keep disabled until then.
import Foundation
import HealthKit

@MainActor
final class HeartRate: NSObject, ObservableObject {
    @Published private(set) var bpm: Double?
    @Published private(set) var authorised = false
    private let store = HKHealthStore()
    private var query: HKAnchoredObjectQuery?
    private(set) var samples: [Double] = []

    var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    /// Shows the system permission sheet. Only ever called from an explicit tap on "Turn on heart rate".
    func requestPermission() async {
        guard isAvailable, let type = HKObjectType.quantityType(forIdentifier: .heartRate) else { return }
        do { try await store.requestAuthorization(toShare: [], read: [type]); authorised = true } catch { authorised = false }
    }

    func start(from date: Date) {
        guard authorised, query == nil, let type = HKObjectType.quantityType(forIdentifier: .heartRate) else { return }
        let unit = HKUnit.count().unitDivided(by: .minute())
        let handle: (HKAnchoredObjectQuery, [HKSample]?, [HKDeletedObject]?, HKQueryAnchor?, Error?) -> Void = { [weak self] _, new, _, _, _ in
            let values = (new as? [HKQuantitySample] ?? []).map { $0.quantity.doubleValue(for: unit) }
            guard !values.isEmpty else { return }
            Task { @MainActor in self?.samples.append(contentsOf: values); self?.bpm = values.last }
        }
        let q = HKAnchoredObjectQuery(type: type, predicate: HKQuery.predicateForSamples(withStart: date, end: nil), anchor: nil, limit: HKObjectQueryNoLimit, resultsHandler: handle)
        q.updateHandler = handle
        store.execute(q); query = q
    }

    /// Returns average and peak for the session, then forgets the readings.
    func stop() -> (avg: Int, peak: Int)? {
        if let q = query { store.stop(q) }
        query = nil; bpm = nil
        defer { samples = [] }
        guard !samples.isEmpty else { return nil }
        return (Int((samples.reduce(0, +) / Double(samples.count)).rounded()), Int(samples.max()!.rounded()))
    }
}
