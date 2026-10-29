// 2026-10-28
// 작업자 : 양태건
import 'dart:async';
import 'dart:convert';

import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/view/team/team_detail_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/team_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

http.Response response(Object data, [int code = 200]) =>
    http.Response.bytes(utf8.encode(jsonEncode(data)), code);

Future<ProviderContainer> mount(
  WidgetTester tester,
  Future<http.Response> Function(http.Request) handler,
) async {
  final api = MemberApi(
    client: MockClient((request) async {
      if (request.url.path.startsWith('/team/applications/')) {
        return response({
          'team': team('captain_01'),
          'can_manage': true,
          'results': [],
        });
      }
      return handler(request);
    }),
  );
  final container = ProviderContainer(
    overrides: [memberApiProvider.overrideWithValue(api)],
  );
  container.read(sessionProvider.notifier).signIn({
    'c_id': 'captain',
    'preferred_stocks': [1],
  });
  addTearDown(() {
    container.dispose();
    api.client.close();
  });
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(home: TeamDetailPage(id: 3)),
    ),
  );
  await tester.pumpAndSettle();
  return container;
}

Map<String, dynamic> team(String captain, {bool closed = false}) => {
  't_id': 3,
  't_name': '테스트 팀',
  'captain_id': captain,
  'captain_name': captain,
  'member_count': 2,
  'is_closed': closed,
};

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 실제 DB 쓰기 없이 서버 거절·재시도·권한 갱신·중복 제출을 확인합니다.
void main() {
  testWidgets('팀장 위임 실패 시 입력 유지, 성공 시 권한 제거', (tester) async {
    String captain = 'captain_01';
    int calls = 0;
    await mount(tester, (request) async {
      if (request.method == 'GET') return response(team(captain));
      expect(request.url.path, '/team/captain/3');
      expect(jsonDecode(request.body), {
        'c_id_seq': 'captain_01',
        'new_captain': 'member_01',
      });
      calls++;
      if (calls == 1) {
        return response({'detail': '새 팀장은 이 팀의 현재 팀원이어야 합니다.'}, 409);
      }
      captain = 'member_01';
      return response({'result': 'OK'}, 201);
    });
    await tester.ensureVisible(find.text('팀장 위임'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('팀장 위임'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), 'captain_01');
    await tester.tap(find.widgetWithText(FilledButton, '팀장 위임'));
    await tester.pumpAndSettle();
    expect(find.text('본인에게는 위임할 수 없습니다.'), findsOneWidget);
    expect(calls, 0);
    await tester.enterText(find.byType(TextFormField), 'member_01');
    for (var i = 0; i < 2; i++) {
      await tester.tap(find.widgetWithText(FilledButton, '팀장 위임'));
      await tester.pumpAndSettle();
      expect(find.textContaining('결제 기록은 기존 결제자에게 유지'), findsOneWidget);
      await tester.tap(find.text('위임 확정'));
      await tester.pumpAndSettle();
      if (i == 0) {
        expect(find.textContaining('새 팀장은 이 팀의 현재 팀원이어야 합니다.'), findsOneWidget);
        expect(
          tester
              .widget<TextFormField>(find.byType(TextFormField))
              .controller!
              .text,
          'member_01',
        );
      }
    }
    expect(calls, 2);
    expect(find.text('팀장 위임'), findsNothing);
    expect(find.text('팀 폐지'), findsNothing);
    expect(find.text('팀 탈퇴'), findsOneWidget);
  });

  testWidgets('팀원 및 폐지된 팀에는 위임 버튼 없음', (tester) async {
    bool closed = false;
    final container = await mount(
      tester,
      (_) async => response(team('member_01', closed: closed)),
    );
    expect(find.text('팀장 위임'), findsNothing);
    closed = true;
    // 회원 전환으로 팀 상세를 다시 조회하여 폐지된 팀장 권한도 숨깁니다.
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'member',
      'preferred_stocks': [1],
    });
    await tester.pumpAndSettle();
    expect(find.text('폐지된 팀'), findsOneWidget);
    expect(find.text('팀장 위임'), findsNothing);
  });

  test('진행 중 중복 요청 차단 및 계정 전환 후 늦은 성공 무시', () async {
    final pending = Completer<http.Response>();
    int calls = 0;
    final api = MemberApi(
      client: MockClient((_) {
        calls++;
        return pending.future;
      }),
    );
    final container = ProviderContainer(
      overrides: [memberApiProvider.overrideWithValue(api)],
    );
    addTearDown(() {
      container.dispose();
      api.client.close();
    });
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'captain',
      'preferred_stocks': [1],
    });
    const key = (teamId: 3, memberId: 'captain_01');
    final subscription = container.listen(
      captainTransferProvider(key),
      (_, _) {},
    );
    addTearDown(subscription.close);
    final notifier = container.read(captainTransferProvider(key).notifier);
    final first = notifier.submit('member_01');
    expect(await notifier.submit('member_01'), false);
    await Future<void>.delayed(Duration.zero);
    expect(calls, 1);
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'other',
      'preferred_stocks': [1],
    });
    pending.complete(response({'result': 'OK'}, 201));
    expect(await first, false);
    expect(container.read(captainTransferProvider(key)), false);
  });
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
