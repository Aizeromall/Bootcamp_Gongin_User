// 작업자 : 최현준 (수정)
// 최초 작업 일 : 기존 생성 이력 유지 / 수정 일 : 2026-10-28
import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
    // SDK를 호출하지 않고 설치된 앱의 공개 OAuth 설정만 확인합니다.
    guard let registrar = engineBridge.pluginRegistry.registrar(forPlugin: "GonginSocialPreflight") else {
      return
    }
    let channel = FlutterMethodChannel(name: "gongin/social_preflight", binaryMessenger: registrar.messenger())
    channel.setMethodCallHandler { call, result in
      guard call.method == "settings" else {
        result(FlutterMethodNotImplemented)
        return
      }
      let info = Bundle.main.infoDictionary ?? [:]
      let firebaseInfo = Bundle.main.url(forResource: "GoogleService-Info", withExtension: "plist")
        .flatMap { NSDictionary(contentsOf: $0) as? [String: Any] } ?? [:]
      let configured = (info["GIDClientID"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
      let schemes = (info["CFBundleURLTypes"] as? [[String: Any]] ?? [])
        .flatMap { $0["CFBundleURLSchemes"] as? [String] ?? [] }
      // Secret/토큰/계정 정보는 반환하지 않습니다.
      result(["googleClientId": configured.isEmpty ? firebaseInfo["CLIENT_ID"] as? String ?? "" : configured,
              "schemes": schemes])
    }
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
