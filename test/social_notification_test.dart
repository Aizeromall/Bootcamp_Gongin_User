// 작업자 : 최현준
// 최초 작업 일 : 2026-10-28
import 'dart:async';
import 'dart:convert';

import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/service/notification_service.dart';
import 'package:bootcamp_project_gongin_admin_app/view/auth/login_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/notification_state.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/social_login_state.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class FakeNotifications extends NotificationService {
  final tokens = StreamController<String>.broadcast();
  final messages = StreamController<RemoteMessage>.broadcast();
  final taps = StreamController<RemoteMessage>.broadcast();
  String? token = 'device-one';
  int deleted = 0;
  RemoteMessage? initial;
  @override
  bool get supported => true;
  @override
  Stream<String> get refreshes => tokens.stream;
  @override
  Stream<RemoteMessage> get foreground => messages.stream;
  @override
  Stream<RemoteMessage> get opened => taps.stream;
  @override
  Future<RemoteMessage?> initialMessage() async => initial;
  @override
  Future<String?> requestToken() async => token;
  @override
  Future<void> deleteToken() async {
    deleted++;
  }

  Future<void> close() async {
    await tokens.close();
    await messages.close();
    await taps.close();
  }
}

const member = {
  'c_id': 'member',
  'c_id_seq': 'member_01',
  'c_name': '회원',
  'member_ids': ['member_01', 'member_04'],
  'preferred_stocks': [1, 4],
  'access_token': 'service-jwt',
};

Future<void> settle() async {
  for (var i = 0; i < 8; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  test('종료 상태 알림은 로그인 후 소유 회원만 열고 등록 실패를 재시도', () async {
    final sdk = FakeNotifications()
      ..initial = const RemoteMessage(
        data: {
          'event_id': '11',
          'type': 'match_confirmed',
          'c_id_seq': 'member_04',
          'r_seq': '7',
        },
      );
    var fail = true;
    final api = MemberApi(
      client: MockClient(
        (_) async => http.Response(
          fail ? '{"detail":"로그인이 만료되었습니다."}' : '{"result":"OK"}',
          fail ? 401 : 200,
        ),
      ),
    );
    final container = ProviderContainer(
      overrides: [
        memberApiProvider.overrideWithValue(api),
        notificationServiceProvider.overrideWithValue(sdk),
      ],
    );
    addTearDown(() async {
      container.dispose();
      api.client.close();
      await sdk.close();
    });
    container.read(notificationProvider);
    await settle();
    expect(container.read(notificationProvider)['message'], isNull);
    container.read(sessionProvider.notifier).signIn(member);
    await settle();
    expect(container.read(notificationProvider)['message']['r_seq'], '7');
    expect(container.read(notificationProvider)['open'], true);
    expect(container.read(notificationProvider)['status'], contains('실패'));
    fail = false;
    await container.read(notificationProvider.notifier).retry();
    expect(container.read(notificationProvider)['status'], contains('모든 종목'));
  });

  test('로그아웃 API 실패에도 로컬 기기 주소 폐기', () async {
    final sdk = FakeNotifications();
    final api = MemberApi(
      client: MockClient(
        (request) async => http.Response(
          request.url.path.endsWith('deactivate') ? '{"detail":"연결 오류"}' : '{}',
          request.url.path.endsWith('deactivate') ? 500 : 200,
        ),
      ),
    );
    final container = ProviderContainer(
      overrides: [
        memberApiProvider.overrideWithValue(api),
        notificationServiceProvider.overrideWithValue(sdk),
      ],
    );
    addTearDown(() async {
      container.dispose();
      api.client.close();
      await sdk.close();
    });
    container.read(notificationProvider);
    container.read(sessionProvider.notifier).signIn(member);
    await settle();
    container.read(sessionProvider.notifier).signOut();
    await settle();
    expect(sdk.deleted, 1);
    expect(container.read(sessionProvider), isNull);
  });

  test('FCM 등록·토큰 갱신·모든 종목 수신·타 계정 차단·로그아웃 해제', () async {
    final sdk = FakeNotifications();
    final requests = <http.Request>[];
    final api = MemberApi(
      client: MockClient((request) async {
        requests.add(request);
        return http.Response('{"result":"OK"}', 200);
      }),
    );
    final container = ProviderContainer(
      overrides: [
        memberApiProvider.overrideWithValue(api),
        notificationServiceProvider.overrideWithValue(sdk),
      ],
    );
    addTearDown(() async {
      container.dispose();
      api.client.close();
      await sdk.close();
    });
    container.read(notificationProvider);
    container.read(sessionProvider.notifier).signIn(member);
    await settle();
    expect(requests.single.url.path, '/notifications/devices');
    expect(requests.single.headers['Authorization'], 'Bearer service-jwt');
    expect(jsonDecode(requests.single.body)['c_id_seq'], 'member_01');
    sdk.tokens.add('device-two');
    await settle();
    expect(jsonDecode(requests.last.body)['f_token'], 'device-two');
    sdk.messages.add(
      const RemoteMessage(
        data: {
          'event_id': '1',
          'type': 'before10',
          'c_id_seq': 'member_04',
          'r_seq': '7',
        },
      ),
    );
    await settle();
    expect(
      container.read(notificationProvider)['message']['c_id_seq'],
      'member_04',
    );
    container.read(notificationProvider.notifier).clearMessage();
    sdk.messages.add(
      const RemoteMessage(
        data: {'event_id': '2', 'type': 'message', 'c_id_seq': 'other_01'},
      ),
    );
    await settle();
    expect(container.read(notificationProvider)['message'], isNull);
    container.read(sessionProvider.notifier).signOut();
    await settle();
    expect(requests.last.url.path, '/notifications/devices/deactivate');
    expect(sdk.deleted, 1);
  });

  test('알림 권한 거부는 등록 요청 없이 안내', () async {
    final sdk = FakeNotifications()..token = null;
    final api = MemberApi(
      client: MockClient((_) async => throw StateError('등록하면 안 됨')),
    );
    final container = ProviderContainer(
      overrides: [
        memberApiProvider.overrideWithValue(api),
        notificationServiceProvider.overrideWithValue(sdk),
      ],
    );
    addTearDown(() async {
      container.dispose();
      api.client.close();
      await sdk.close();
    });
    container.read(notificationProvider);
    container.read(sessionProvider.notifier).signIn(member);
    await settle();
    expect(container.read(notificationProvider)['status'], contains('알림 권한'));
  });

  testWidgets('간편 로그인 버튼·중복 제출 차단·로그인 세션 반영', (tester) async {
    final completion = Completer<Map<String, dynamic>>();
    var count = 0;
    final container = ProviderContainer(
      overrides: [
        socialLoginProvider.overrideWithValue((provider) {
          expect(provider, 'kakao');
          count++;
          return completion.future;
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
    expect(find.byKey(const ValueKey('social-google')), findsOneWidget);
    expect(find.byKey(const ValueKey('social-naver')), findsOneWidget);
    expect(find.byType(Image), findsNWidgets(3));
    final assets = tester
        .widgetList<Image>(find.byType(Image))
        .map((image) => (image.image as AssetImage).assetName)
        .toSet();
    expect(assets, contains('assets/images/kakao_login_en_medium.png'));
    expect(
      assets,
      contains('assets/images/NAVER_login_Light_KR_green_narrow_H56.png'),
    );
    expect(
      assets,
      contains(
        'assets/images/Theme=Light, Show text=Yes, Shape=Square, Platform=Android+Web@4x.png',
      ),
    );
    await tester.ensureVisible(find.byKey(const ValueKey('social-kakao')));
    await tester.tap(find.byKey(const ValueKey('social-kakao')));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('social-kakao')));
    await tester.pump();
    expect(count, 1);
    completion.complete(member);
    await tester.pumpAndSettle();
    expect(container.read(sessionProvider)?['c_id'], 'member');
  });

  testWidgets('간편가입 시 기존 가입 화면 재사용 및 비밀번호 미노출', (tester) async {
    final container = ProviderContainer(
      overrides: [
        socialLoginProvider.overrideWithValue(
          (_) async => {
            'signup_required': true,
            'signup_ticket': 'one-time-ticket',
          },
        ),
      ],
    );
    addTearDown(container.dispose);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: LoginPage()),
      ),
    );
    await tester.ensureVisible(find.byKey(const ValueKey('social-naver')));
    await tester.tap(find.byKey(const ValueKey('social-naver')));
    await tester.pumpAndSettle();
    expect(find.text('기본 정보를 입력해 주세요'), findsOneWidget);
    expect(find.byKey(const ValueKey('c_pw')), findsNothing);
    expect(find.byKey(const ValueKey('c_phone')), findsOneWidget);
  });
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
