// 작업자 : 최현준
// 최초 작업 일 : 2026-10-28
// 기존 서버 Firebase Admin Message(token=...) 계약을 유지하기 위해 FID가 아닌 FCM 토큰 API를 사용합니다.
// ignore_for_file: deprecated_member_use
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

/// 기기 SDK만 담당합니다. 등록·해제와 회원 상태는 Riverpod에서 관리합니다.
class NotificationService {
  bool get supported =>
      !kIsWeb &&
      defaultTargetPlatform == TargetPlatform.android &&
      Firebase.apps.isNotEmpty;
  Stream<String> get refreshes => supported
      ? FirebaseMessaging.instance.onTokenRefresh
      : const Stream.empty();
  Stream<RemoteMessage> get foreground =>
      supported ? FirebaseMessaging.onMessage : const Stream.empty();
  Stream<RemoteMessage> get opened =>
      supported ? FirebaseMessaging.onMessageOpenedApp : const Stream.empty();

  Future<RemoteMessage?> initialMessage() async =>
      supported ? FirebaseMessaging.instance.getInitialMessage() : null;

  Future<String?> requestToken() async {
    if (!supported) return null;
    final settings = await FirebaseMessaging.instance.requestPermission();
    if (settings.authorizationStatus != AuthorizationStatus.authorized &&
        settings.authorizationStatus != AuthorizationStatus.provisional) {
      return null;
    }
    return FirebaseMessaging.instance.getToken();
  }

  Future<void> deleteToken() async {
    if (supported) await FirebaseMessaging.instance.deleteToken();
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
