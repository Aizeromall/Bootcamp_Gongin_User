// 작업자 : 최현준
// 최초 작업 일 : 2026-10-28
import 'dart:async';

import 'package:bootcamp_project_gongin_admin_app/service/social_login_service.dart';
import 'package:bootcamp_project_gongin_admin_app/service/social_login_exception.dart';
import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/view/auth/login_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/social_login_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:kakao_flutter_sdk_user/kakao_flutter_sdk_user.dart';

const client = '123-test.apps.googleusercontent.com';
const key = '0123456789abcdef0123456789abcdef';
const settings = {
  'KAKAO_NATIVE_APP_KEY': key,
  'NAVER_CLIENT_ID': 'test-id',
  'NAVER_CLIENT_SECRET': 'test-secret',
  'NAVER_URL_SCHEME': 'gongin-naver',
};
const nativeSettings = {
  'googleClientId': client,
  'schemes': [
    'com.googleusercontent.apps.123-test',
    'kakao$key',
    'gongin-naver',
  ],
};
Matcher message(String value) => isA<SocialLoginException>().having(
  (e) => e.message,
  'message',
  contains(value),
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final provider in ['google', 'kakao', 'naver']) {
    test('$provider 설정 누락은 SDK 호출 없이 반복 차단', () async {
      var calls = 0;
      final service = SocialLoginService(
        platform: TargetPlatform.iOS,
        settings: const {},
        readNativeSettings: () async => {},
        authenticateSdk: (_, _) async {
          calls++;
          return 'never';
        },
      );
      for (var attempt = 0; attempt < 2; attempt++) {
        await expectLater(
          service.authenticate(provider),
          throwsA(message(SocialLoginService.labels[provider]!)),
        );
      }
      expect(calls, 0);
    });
    test('$provider iOS 콜백 누락 차단 및 유효 설정 성공', () async {
      var calls = 0;
      var schemesReady = false;
      final service = SocialLoginService(
        platform: TargetPlatform.iOS,
        settings: settings,
        readNativeSettings: () async => schemesReady
            ? nativeSettings
            : {'googleClientId': client, 'schemes': []},
        authenticateSdk: (name, googleClient) async {
          calls++;
          expect(name, provider);
          if (name == 'google') expect(googleClient, client);
          return 'mock-token';
        },
      );
      await expectLater(
        service.authenticate(provider),
        throwsA(message('콜백 스킴')),
      );
      expect(calls, 0);
      schemesReady = true;
      expect(await service.authenticate(provider), 'mock-token');
      expect(calls, 1);
    });
  }

  test('실제 MethodChannel 형식의 빈 iOS 설정에서도 SDK 미호출', () async {
    const channel = MethodChannel('gongin/social_preflight');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          expect(call.method, 'settings');
          return {'googleClientId': '', 'schemes': []};
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null),
    );
    final service = SocialLoginService(
      platform: TargetPlatform.iOS,
      authenticateSdk: (_, _) async => throw StateError('SDK를 호출하면 안 됨'),
    );
    await expectLater(
      service.authenticate('google'),
      throwsA(message('Client ID')),
    );
  });

  test('브리지 미등록은 전체 재빌드 안내로 처리', () async {
    final service = SocialLoginService(
      platform: TargetPlatform.iOS,
      readNativeSettings: () async => throw MissingPluginException(),
    );
    await expectLater(
      service.authenticate('google'),
      throwsA(message('다시 빌드')),
    );
  });

  test('Google 취소 후 재시도 가능·원문 비밀값 미노출', () async {
    var attempt = 0;
    final service = SocialLoginService(
      platform: TargetPlatform.iOS,
      settings: settings,
      readNativeSettings: () async => nativeSettings,
      authenticateSdk: (_, _) async {
        if (attempt++ == 0) {
          throw const GoogleSignInException(
            code: GoogleSignInExceptionCode.canceled,
            description: 'secret-should-not-appear',
          );
        }
        return 'mock-token';
      },
    );
    await expectLater(service.authenticate('google'), throwsA(message('취소')));
    expect(await service.authenticate('google'), 'mock-token');
  });

  test('카카오 취소·네이버 SDK 실패 및 동시 인증 차단', () async {
    final pending = Completer<String>();
    final service = SocialLoginService(
      platform: TargetPlatform.iOS,
      settings: settings,
      readNativeSettings: () async => nativeSettings,
      authenticateSdk: (provider, _) async {
        if (provider == 'kakao') {
          throw KakaoClientException(ClientErrorCause.cancelled, 'private');
        }
        if (provider == 'naver') {
          throw PlatformException(code: 'SDK_ERROR', message: 'private-token');
        }
        return pending.future;
      },
    );
    await expectLater(
      service.authenticate('kakao'),
      throwsA(message('카카오 로그인을 취소')),
    );
    await expectLater(
      service.authenticate('naver'),
      throwsA(message('네이버 SDK')),
    );
    final first = service.authenticate('google');
    await expectLater(service.authenticate('google'), throwsA(message('진행 중')));
    pending.complete('mock-token');
    expect(await first, 'mock-token');
  });

  for (final provider in ['google', 'kakao', 'naver']) {
    testWidgets('$provider 설정 안내·서버 오류 구분 및 반복 클릭 후 화면 유지', (tester) async {
      var attempt = 0;
      final label = SocialLoginService.labels[provider]!;
      final container = ProviderContainer(
        overrides: [
          socialLoginProvider.overrideWithValue((_) async {
            if (attempt++ == 0) {
              throw SocialLoginException('$label 앱 설정이 필요합니다.');
            }
            throw const ApiException(503, '인증 서비스 연결 실패');
          }),
        ],
      );
      addTearDown(container.dispose);
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: LoginPage()),
        ),
      );
      final button = find.byKey(ValueKey('social-$provider'));
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.text('$label 앱 설정이 필요합니다.'), findsOneWidget);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.text('$label 서버 오류 (503): 인증 서비스 연결 실패'), findsOneWidget);
      expect(find.byType(LoginPage), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
