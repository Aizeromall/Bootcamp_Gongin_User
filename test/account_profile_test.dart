// 작업자 : 최현준 / 최초 작업 일 : 2026-10-29
import 'dart:async';
import 'dart:convert';

import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/view/account/account_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/account/account_profile_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/auth/login_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/social_login_state.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/account_state.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const session = {
  'c_id': 'member',
  'c_id_seq': 'member_01',
  'c_name': '회원',
  'c_login_type': 'local',
  'access_token': 'mock-jwt',
  'preferred_stocks': [1],
  'member_ids': ['member_01'],
};
Map<String, dynamic> profile({String provider = 'local'}) => {
  'members': [
    {
      'c_id_seq': 'member_01',
      'c_login_type': provider,
      'c_name': '회원',
      'c_address': '서울',
      'c_phone': '01012345678',
      'c_gender': '남성',
      'c_birthday': '2000-01-01',
      'c_prefer_stock': '1',
      'c_position': 'FW',
      'c_rating': 1500,
      'c_deletdate': null,
    },
  ],
};
http.Response response(Object body, [int status = 200]) => http.Response(
  jsonEncode(body),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

Future<ProviderContainer> setup(
  WidgetTester tester,
  FutureOr<http.Response> Function(http.Request) handler, {
  bool card = false,
}) async {
  final container = ProviderContainer(
    overrides: [
      memberApiProvider.overrideWithValue(
        MemberApi(client: MockClient((request) async => handler(request))),
      ),
    ],
  );
  addTearDown(container.dispose);
  container
      .read(sessionProvider.notifier)
      .signIn(Map<String, dynamic>.from(session));
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        home: card
            ? Scaffold(
                body: AccountPage(onReservations: () {}, onTeams: () {}),
              )
            : const AccountProfilePage(),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return container;
}

Future<void> bottom(WidgetTester tester, [String target = '계정 삭제']) async {
  FocusManager.instance.primaryFocus?.unfocus();
  await tester.pumpAndSettle();
  await tester.ensureVisible(find.text(target));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('회원정보 전화번호에 입력·붙여넣기한 숫자 외 문자를 제거', (tester) async {
    await setup(tester, (_) => response(profile()));
    final phone = find.byKey(const ValueKey('profile-c_phone'));
    await tester.enterText(phone, '010-12a3 45!67');
    expect(tester.widget<TextFormField>(phone).controller!.text, '0101234567');
  });

  testWidgets('선호 종목 4개 표시·기존 선택·신규 선택의 포지션을 한 PATCH로 저장', (tester) async {
    final writes = <http.Request>[];
    final container = await setup(tester, (request) {
      if (request.method == 'GET') return response(profile());
      writes.add(request);
      return response({
        'result': 'OK',
        'session': {
          ...session,
          'preferred_stocks': [4],
          'member_ids': ['member_04'],
          'c_id_seq': 'member_04',
        },
      });
    }, card: true);
    await tester.tap(find.byType(InkWell).first);
    await tester.pumpAndSettle();
    expect(find.byType(FilterChip), findsNWidgets(4));
    expect(
      tester
          .widget<FilterChip>(find.byKey(const ValueKey('profile-sport-1')))
          .selected,
      isTrue,
    );
    await bottom(tester, '선호 종목 · 포지션');
    await tester.tap(find.byKey(const ValueKey('profile-sport-4')));
    await tester.tap(find.byKey(const ValueKey('profile-sport-1')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(
      find.byKey(const ValueKey('profile-position-4')),
    );
    await tester.tap(find.byKey(const ValueKey('profile-position-4')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('세터').last);
    await tester.pumpAndSettle();
    await bottom(tester, '저장');
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();
    expect(writes, isEmpty);
    expect(find.text('선호 종목 삭제 신청'), findsOneWidget);
    await tester.tap(find.widgetWithText(TextButton, '저장'));
    await tester.pumpAndSettle();
    expect(writes.single.method, 'PATCH');
    expect(jsonDecode(writes.single.body), {
      'preferred_stocks': [4],
      'c_position': {'4': '세터'},
    });
    expect(container.read(sportProvider), 4);
  });

  testWidgets('삭제 유예 종목도 표시하고 재선택하면 일괄 복구 요청', (tester) async {
    http.Request? write;
    await setup(tester, (request) {
      if (request.method == 'GET') {
        final data = profile();
        data['members'] = [
          ...(data['members'] as List),
          <String, dynamic>{
            ...Map<String, dynamic>.from(
              (data['members'] as List).first as Map,
            ),
            'c_id_seq': 'member_04',
            'c_prefer_stock': '4',
            'c_position': '세터',
            'c_deletdate': '2026-10-28T12:00:00',
          },
        ];
        return response(data);
      }
      write = request;
      return response({
        'result': 'OK',
        'session': {
          ...session,
          'preferred_stocks': [1, 4],
        },
      });
    }, card: true);
    await tester.tap(find.byType(InkWell).first);
    await tester.pumpAndSettle();
    await bottom(tester, '선호 종목 · 포지션');
    expect(
      tester
          .widget<FilterChip>(find.byKey(const ValueKey('profile-sport-4')))
          .selected,
      isFalse,
    );
    await tester.tap(find.byKey(const ValueKey('profile-sport-4')));
    await tester.pumpAndSettle();
    await bottom(tester, '저장');
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();
    expect(jsonDecode(write!.body), {
      'preferred_stocks': [1, 4],
      'c_position': {'1': 'FW', '4': '세터'},
    });
  });

  testWidgets('모든 종목 해제는 확인 후 저장하며 성공하면 로그아웃', (tester) async {
    var writes = 0;
    final container = await setup(tester, (request) {
      if (request.method == 'GET') return response(profile());
      writes++;
      expect(jsonDecode(request.body), {
        'preferred_stocks': [],
        'c_position': {},
      });
      return response({
        'result': 'OK',
        'session': {
          'recovery_required': true,
          'recovery_token': 'mock-recovery',
        },
      });
    });
    await bottom(tester, '선호 종목 · 포지션');
    await tester.tap(find.byKey(const ValueKey('profile-sport-1')));
    await tester.pumpAndSettle();
    await bottom(tester, '저장');
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('취소'));
    await tester.pumpAndSettle();
    expect(writes, 0);
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, '저장'));
    await tester.pumpAndSettle();
    expect(writes, 1);
    expect(container.read(sessionProvider), isNull);
  });

  for (final yes in [false, true]) {
    testWidgets('삭제 계정 로그인 복구 확인 ${yes ? '예' : '아니오'}', (tester) async {
      final calls = <http.Request>[];
      final container = ProviderContainer(
        overrides: [
          memberApiProvider.overrideWithValue(
            MemberApi(
              client: MockClient((request) async {
                calls.add(request);
                if (request.url.path == '/auth/login') {
                  return response({
                    'recovery_required': true,
                    'recovery_token': 'mock-recovery',
                    'sports': [
                      {'sport': 1, 'state': 'recoverable'},
                      {'sport': 4, 'state': 'expired'},
                    ],
                  });
                }
                expect(request.url.path, '/auth/account/recovery/restore');
                expect(
                  request.headers['Authorization'],
                  'Bearer mock-recovery',
                );
                expect(jsonDecode(request.body), {
                  'sports': [1],
                });
                return response({'result': 'OK', 'session': session});
              }),
            ),
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
      await tester.enterText(
        find.widgetWithText(TextFormField, '아이디'),
        'member',
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, '비밀번호'),
        'password123',
      );
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.ensureVisible(find.widgetWithText(FilledButton, '로그인'));
      await tester.tap(find.widgetWithText(FilledButton, '로그인'));
      await tester.pumpAndSettle();
      expect(find.text('계정 복구'), findsOneWidget);
      expect(container.read(sessionProvider), isNull);
      await tester.tap(find.text(yes ? '예' : '아니오'));
      await tester.pumpAndSettle();
      expect(calls.length, yes ? 2 : 1);
      expect(container.read(sessionProvider)?['c_id'], yes ? 'member' : null);
    });
  }

  testWidgets('간편로그인도 복구 확인부터 진행하고 아니오에서는 인증 세션 없음', (tester) async {
    final container = ProviderContainer(
      overrides: [
        socialLoginProvider.overrideWithValue(
          (_) async => {
            'recovery_required': true,
            'recovery_token': 'mock-recovery',
            'sports': [
              {'sport': 1, 'state': 'recoverable'},
            ],
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
    await tester.ensureVisible(find.byKey(const ValueKey('social-google')));
    await tester.tap(find.byKey(const ValueKey('social-google')));
    await tester.pumpAndSettle();
    expect(find.text('계정 복구'), findsOneWidget);
    await tester.tap(find.text('아니오'));
    await tester.pumpAndSettle();
    expect(container.read(sessionProvider), isNull);
  });

  testWidgets('MY 카드로 진입한 뒤 본인 인증 헤더로 조회', (tester) async {
    final calls = <http.Request>[];
    await setup(tester, (request) {
      calls.add(request);
      return response(profile());
    }, card: true);
    expect(
      calls.where((request) => request.url.path == '/auth/account'),
      isEmpty,
    );
    await tester.tap(find.byType(InkWell).first);
    await tester.pumpAndSettle();
    expect(find.text('회원정보 수정'), findsOneWidget);
    final accountCall = calls.singleWhere(
      (request) => request.url.path == '/auth/account',
    );
    expect(accountCall.headers['Authorization'], 'Bearer mock-jwt');
  });

  testWidgets('조회 실패는 오류와 재시도 경로 제공', (tester) async {
    var calls = 0;
    await setup(
      tester,
      (_) => ++calls == 1
          ? response({'detail': '조회 실패'}, 500)
          : response(profile()),
    );
    expect(find.textContaining('조회 실패'), findsOneWidget);
    await tester.tap(find.text('다시 시도'));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('profile-c_name')), findsOneWidget);
    expect(calls, 2);
  });

  testWidgets('빈 프로필은 수정 폼 대신 오류 표시', (tester) async {
    await setup(tester, (_) => response({'members': []}));
    expect(find.textContaining('회원정보 응답을 확인할 수 없습니다.'), findsOneWidget);
    expect(find.byKey(const ValueKey('profile-c_name')), findsNothing);
  });

  testWidgets('작은 화면·키보드 환경에서도 삭제 안내 취소 가능', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await setup(tester, (_) => response(profile()));
    await tester.tap(find.byKey(const ValueKey('profile-c_name')));
    await bottom(tester);
    await tester.tap(find.text('계정 삭제'));
    await tester.pumpAndSettle();
    expect(find.text('계정 삭제 안내 및 동의'), findsOneWidget);
    await tester.tap(find.text('취소'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('프로필 저장은 PATCH 변경 필드만 전송하고 세션 갱신', (tester) async {
    final writes = <http.Request>[];
    final container = await setup(tester, (request) {
      if (request.method == 'GET') return response(profile());
      writes.add(request);
      return response({
        'result': 'OK',
        'session': {...session, 'c_name': '변경회원', 'access_token': 'new-jwt'},
      });
    }, card: true);
    await tester.tap(find.byType(InkWell).first);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const ValueKey('profile-c_name')),
      '변경회원',
    );
    await bottom(tester, '저장');
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();
    expect(writes.single.method, 'PATCH');
    expect(writes.single.url.path, '/auth/account/profile');
    expect(jsonDecode(writes.single.body), {'c_name': '변경회원'});
    expect(container.read(sessionProvider)?['c_name'], '변경회원');
    expect(find.byType(AccountProfilePage), findsNothing);
  });

  testWidgets('저장 실패 시 수정 입력과 계정 유지', (tester) async {
    final container = await setup(
      tester,
      (request) => request.method == 'GET'
          ? response(profile())
          : response({'detail': '저장 실패'}, 422),
    );
    await tester.enterText(
      find.byKey(const ValueKey('profile-c_name')),
      '변경회원',
    );
    await bottom(tester, '저장');
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();
    expect(find.textContaining('저장 실패'), findsOneWidget);
    expect(container.read(sessionProvider)?['c_name'], '회원');
    await tester.drag(find.byType(Scrollable).first, const Offset(0, 2000));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<TextFormField>(find.byKey(const ValueKey('profile-c_name')))
          .controller!
          .text,
      '변경회원',
    );
  });

  testWidgets('삭제 약관 미동의·취소에서는 요청 없음, 동의 후 서버 성공시에만 로그아웃', (tester) async {
    var deletes = 0;
    final completion = Completer<http.Response>();
    final container = await setup(tester, (request) {
      if (request.method == 'GET') return response(profile());
      deletes++;
      expect(request.url.path, '/auth/account/withdraw');
      expect(request.method, 'POST');
      return completion.future;
    });
    await bottom(tester);
    await tester.tap(find.text('계정 삭제'));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<TextButton>(find.widgetWithText(TextButton, '삭제 신청'))
          .onPressed,
      isNull,
    );
    await tester.tap(find.text('취소'));
    await tester.pumpAndSettle();
    expect(deletes, 0);
    await tester.tap(find.text('계정 삭제'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    await tester.tap(find.text('삭제 신청'));
    await tester.pump();
    expect(deletes, 1);
    expect(container.read(sessionProvider), isNotNull);
    // 수정 일 : 2026-10-31 / 작업자 : 신현진 — AsyncNotifier 변환으로 처리 중 여부는 isLoading
    expect(container.read(accountActionsProvider).isLoading, isTrue);
    completion.complete(
      response({
        'result': 'OK',
        'session': {
          'recovery_required': true,
          'recovery_token': 'mock-recovery',
        },
      }),
    );
    await tester.pumpAndSettle();
    expect(container.read(sessionProvider), isNull);
    expect(deletes, 1);
  });

  testWidgets('삭제 신청 실패 시 로그아웃하지 않고 재시도 가능', (tester) async {
    final container = await setup(
      tester,
      (request) => request.method == 'GET'
          ? response(profile())
          : response({'detail': '삭제 신청 실패'}, 500),
    );
    await bottom(tester);
    await tester.tap(find.text('계정 삭제'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    await tester.tap(find.text('삭제 신청'));
    await tester.pumpAndSettle();
    expect(container.read(sessionProvider), isNotNull);
    // 수정 일 : 2026-10-31 / 작업자 : 신현진 — 처리 중 여부는 isLoading
    expect(container.read(accountActionsProvider).isLoading, isFalse);
    expect(find.textContaining('삭제 신청 실패'), findsOneWidget);
  });

  testWidgets('간편가입자는 비밀번호 입력 없이 프로필 수정', (tester) async {
    await setup(tester, (_) => response(profile(provider: 'naver')));
    await bottom(tester);
    expect(find.text('비밀번호 변경 (선택)'), findsNothing);
    expect(find.text('계정 삭제'), findsOneWidget);
  });

  test('늦은 저장 응답이 다른 로그인 계정을 덮지 않음·중복 저장 차단', () async {
    final pending = Completer<http.Response>();
    var calls = 0;
    final container = ProviderContainer(
      overrides: [
        memberApiProvider.overrideWithValue(
          MemberApi(
            client: MockClient((_) {
              calls++;
              return pending.future;
            }),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    container
        .read(sessionProvider.notifier)
        .signIn(Map<String, dynamic>.from(session));
    final action = container.read(accountActionsProvider.notifier);
    final first = action.save({'c_name': '변경회원'});
    final rejected = expectLater(first, throwsA(isA<ApiException>()));
    await expectLater(
      action.save({'c_name': '중복'}),
      throwsA(isA<ApiException>()),
    );
    container.read(sessionProvider.notifier).signIn({
      ...session,
      'c_id': 'other',
    });
    pending.complete(
      response({
        'result': 'OK',
        'session': {...session, 'c_name': '변경회원'},
      }),
    );
    await rejected;
    expect(container.read(sessionProvider)?['c_id'], 'other');
    expect(calls, 1);
  });
}
// 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-31 / 작업자 : 신현진 (동작 Notifier AsyncNotifier 변환에 맞춰 isLoading 사용)
