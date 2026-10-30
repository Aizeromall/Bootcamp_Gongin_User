// 2026-10-30
// 작업자 : 김병재
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:bootcamp_project_gongin_admin_app/app.dart';
import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/service/session_storage.dart';
import 'package:bootcamp_project_gongin_admin_app/view/home/member_home.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/auth_refresh_state.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/chat_state.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:bootcamp_project_gongin_admin_app/view/chat/chat_page.dart';

http.Response response(Object data, [int code = 200]) =>
    http.Response.bytes(utf8.encode(jsonEncode(data)), code);

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 기기 보안 저장소 대신 사용하는 메모리 저장소입니다.
class MemoryStorage extends SessionStorage {
  MemoryStorage([this.value]);
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> save(String token) async => value = token;
  @override
  Future<void> clear() async => value = null;
}

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 실제 memberApiProvider와 같은 방식으로 401 갱신 함수를 연결한 테스트용 컨테이너입니다.
ProviderContainer containerFor(
  Future<http.Response> Function(http.Request) handler, {
  MemoryStorage? storage,
  bool signedIn = true,
}) {
  final client = MockClient(handler);
  final container = ProviderContainer(
    overrides: [
      memberApiProvider.overrideWith(
        (ref) => MemberApi(
          client: client,
          onUnauthorized: (expired) =>
              ref.read(authRefreshProvider).renew(expired),
        ),
      ),
      sessionStorageProvider.overrideWithValue(storage ?? MemoryStorage()),
    ],
  );
  if (signedIn) {
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'member',
      'c_name': '회원',
      'c_id_seq': 'member_01',
      'member_ids': ['member_01', 'member_02'],
      'preferred_stocks': [1, 2],
      'access_token': 'old-jwt',
    });
  }
  addTearDown(() {
    container.dispose();
    client.close();
  });
  return container;
}

void main() {
  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  test('로그인 JWT 만료 시 /auth/refresh 후 같은 요청을 새 토큰으로 재시도', () async {
    final calls = <String>[];
    final storage = MemoryStorage('old-jwt');
    final container = containerFor((r) async {
      calls.add('${r.url.path} ${r.headers['Authorization']}');
      if (r.url.path == '/auth/refresh') {
        return response({'c_id': 'member', 'access_token': 'new-jwt'});
      }
      return r.headers['Authorization'] == 'Bearer new-jwt'
          ? response({'result': 'OK'})
          : response({'detail': '만료'}, 401);
    }, storage: storage);
    final before = container.read(sessionProvider);
    final api = container.read(memberApiProvider);
    // 동시에 401을 받아도 갱신 요청은 한 번만 보냅니다.
    final results = await Future.wait([
      api.request('/auth/account', accessToken: 'old-jwt'),
      api.request('/my_team', accessToken: 'old-jwt'),
    ]);
    expect(results.every((r) => r['result'] == 'OK'), true);
    expect(calls.where((c) => c.startsWith('/auth/refresh')), [
      '/auth/refresh Bearer old-jwt',
    ]);
    // 세션 객체는 그대로 두고 토큰만 바뀌어 계정 전환 검사(identical)가 유지됩니다.
    expect(identical(before, container.read(sessionProvider)), true);
    expect(container.read(sessionProvider)!['access_token'], 'new-jwt');
    // 다음 앱 실행의 자동 로그인을 위해 보안 저장소도 새 토큰으로 바뀝니다.
    expect(storage.value, 'new-jwt');
  });

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  testWidgets('앱 재실행 시 저장된 토큰으로 자동 로그인하고 로그아웃 시 저장 토큰 삭제', (tester) async {
    final storage = MemoryStorage('saved-jwt');
    final container = containerFor(
      (r) async {
        if (r.url.path == '/auth/refresh') {
          expect(r.headers['Authorization'], 'Bearer saved-jwt');
          return response({
            'result': 'OK',
            'c_id': 'member',
            'c_name': '회원',
            'c_id_seq': 'member_02',
            'member_ids': ['member_02'],
            'preferred_stocks': [2],
            'access_token': 'restored-jwt',
          });
        }
        return response({'results': []});
      },
      storage: storage,
      signedIn: false,
    );
    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const MyApp()),
    );
    await tester.pumpAndSettle();
    expect(find.byType(MemberHome), findsOneWidget);
    expect(container.read(sessionProvider)!['access_token'], 'restored-jwt');
    // 가입 종목(농구)이 선택되고 새 토큰이 저장됩니다.
    expect(container.read(sportProvider), 2);
    expect(storage.value, 'restored-jwt');
    container.read(sessionProvider.notifier).signOut();
    await tester.pumpAndSettle();
    expect(storage.value, isNull);
  });

  testWidgets('저장 토큰이 거절되면 삭제하고 시작 화면 표시', (tester) async {
    final storage = MemoryStorage('expired-jwt');
    final container = containerFor(
      (r) async => response({'detail': '로그인 정보가 만료되었습니다.'}, 401),
      storage: storage,
      signedIn: false,
    );
    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const MyApp()),
    );
    await tester.pumpAndSettle();
    expect(find.byType(MemberHome), findsNothing);
    expect(container.read(sessionProvider), isNull);
    expect(storage.value, isNull);
  });

  test('갱신이 거절되면 원래 401을 전달하고 반복 요청하지 않음', () async {
    var refreshCalls = 0;
    final container = containerFor((r) async {
      if (r.url.path == '/auth/refresh') refreshCalls++;
      return response({'detail': '로그인 정보가 만료되었습니다.'}, 401);
    });
    await expectLater(
      container
          .read(memberApiProvider)
          .request('/auth/account', accessToken: 'old-jwt'),
      throwsA(
        isA<ApiException>().having((e) => e.statusCode, 'statusCode', 401),
      ),
    );
    expect(refreshCalls, 1);
    expect(container.read(sessionProvider)!['access_token'], 'old-jwt');
  });

  test('갱신 중 다른 계정으로 바뀌면 이전 계정 토큰을 저장하지 않음', () async {
    late ProviderContainer container;
    container = containerFor((r) async {
      if (r.url.path == '/auth/refresh') {
        container.read(sessionProvider.notifier).signIn({
          'c_id': 'other',
          'access_token': 'other-jwt',
        });
        return response({'c_id': 'member', 'access_token': 'new-jwt'});
      }
      return response({'detail': '만료'}, 401);
    });
    await expectLater(
      container
          .read(memberApiProvider)
          .request('/auth/account', accessToken: 'old-jwt'),
      throwsA(isA<ApiException>()),
    );
    expect(container.read(sessionProvider)!['access_token'], 'other-jwt');
  });

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 전 종목 채팅방: 종목 ID마다 채팅 토큰을 받아 방 목록을 합치고, 같은 방은 한 번만 표시합니다.
  testWidgets('채팅 화면은 비밀번호 없이 자동 인증하고 모든 종목 채팅방을 합쳐 표시', (tester) async {
    final calls = <String>[];
    final container = containerFor((r) async {
      calls.add(r.url.path);
      if (r.url.path == '/chat/session-token') {
        expect(r.headers['Authorization'], 'Bearer old-jwt');
        final id = (jsonDecode(r.body) as Map)['c_id_seq'];
        return response({'access_token': 'chat-$id'});
      }
      expect(r.url.path, '/chat/rooms');
      return switch (r.headers['Authorization']) {
        'Bearer chat-member_01' => response({
          'results': [
            {'me_id': 3, 'me_name': '축구방', 'owner_id': 'member_01'},
            {'me_id': 5, 'me_name': '같이 참여한 방', 'owner_id': 'other_02'},
          ],
        }),
        'Bearer chat-member_02' => response({
          'results': [
            {'me_id': 7, 'me_name': '농구 1:1', 'owner_id': 'other_02'},
            {'me_id': 5, 'me_name': '같이 참여한 방', 'owner_id': 'other_02'},
          ],
        }),
        _ => response({'detail': '권한 없음'}, 403),
      };
    });
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: ChatPage())),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('채팅 로그인'), findsNothing);
    expect(find.byType(TextField), findsNothing);
    expect(container.read(chatTokenProvider), 'chat-member_01');
    // 최근 방(me_id 큰 순)부터, 중복 방은 한 번만, 종목과 역할을 함께 표시합니다.
    expect(find.text('농구 1:1'), findsOneWidget);
    expect(find.text('같이 참여한 방'), findsOneWidget);
    expect(find.text('축구 · 내가 만든 방'), findsOneWidget);
    expect(find.text('농구 · 참여 중'), findsOneWidget);
    expect(
      tester.getTopLeft(find.text('농구 1:1')).dy,
      lessThan(tester.getTopLeft(find.text('축구방')).dy),
    );
    expect(calls.where((p) => p == '/chat/token'), isEmpty);
    // 현재 종목(축구) 토큰은 화면 자동 인증과 목록 조회가 같은 요청을 공유합니다.
    expect(calls.where((p) => p == '/chat/session-token').length, 2);
  });

  test('오래된 채팅 토큰이 만료되면 재발급하고, 방금 발급한 토큰의 거절은 반복하지 않음', () async {
    var issued = 0;
    final container = containerFor((r) async {
      if (r.url.path == '/chat/session-token') {
        issued++;
        return response({'access_token': 'chat-$issued'});
      }
      // chat-2만 유효하고 나머지 채팅 토큰은 거절합니다(권한 없음 등).
      return r.headers['Authorization'] == 'Bearer chat-2'
          ? response({'results': []})
          : response({'detail': '만료'}, 401);
    });
    final api = container.read(memberApiProvider);
    // 이전 화면에서 받아 둔 토큰(발급 시각 기록 없음)은 만료 시 재발급합니다.
    container.read(chatTokenProvider.notifier).setToken('chat-old');
    await expectLater(
      api.request('/chat/rooms', accessToken: 'chat-old'),
      throwsA(isA<ApiException>()),
    );
    expect(container.read(chatTokenProvider), 'chat-1');
    // 방금 발급한 chat-1이 다시 거절되면 60초 안에는 재발급하지 않아 무한 반복을 막습니다.
    await expectLater(
      api.request('/chat/rooms', accessToken: 'chat-1'),
      throwsA(isA<ApiException>()),
    );
    expect(issued, 1);
  });
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
