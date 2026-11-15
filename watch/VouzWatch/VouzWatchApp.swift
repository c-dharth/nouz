// UNBUILT: written without Xcode.
import SwiftUI

@main
struct VouzWatchApp: App {
    @StateObject private var timer = SessionTimer()
    @StateObject private var link = PhoneLink()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(timer)
                .environmentObject(link)
                .onAppear { link.attach(timer) }
        }
    }
}
