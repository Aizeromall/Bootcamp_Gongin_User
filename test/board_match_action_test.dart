// 2026-10-28
// 작업자 : 양태건
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:bootcamp_project_gongin_admin_app/view/board/board_page.dart';

const post = {
  'bulletin_seq': 10,
  'c_id_seq': 'owner_01',
  'c_name': '팀장',
  'event_category': '축구',
  'board_category': '매칭신청',
  'board_title': '상대 팀 모집',
  'board_content': '[예약번호:8]\n경기 소개',
};
http.Response result(Object body, [int status = 200]) =>
    http.Response.bytes(utf8.encode(jsonEncode(body)), status);
ProviderContainer setup(Future<http.Response> Function(http.Request) handler) {
  final api = MemberApi(client: MockClient(handler));
  final container = ProviderContainer(
    overrides: [memberApiProvider.overrideWithValue(api)],
  );
  container.read(sessionProvider.notifier).signIn({
    'c_id': 'member',
    'c_name': '회원',
    'preferred_stocks': [1],
    'access_token': 'mock-token',
  });
  addTearDown(() {
    container.dispose();
    api.client.close();
  });
  return container;
}

Widget app(ProviderContainer container) => UncontrolledProviderScope(
  container: container,
  child: const MaterialApp(home: BoardPage()),
);
void main() {
  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  testWidgets('목록 오른쪽에서 직접 매칭신청하고 중복 신청을 막음', (tester) async {
    var requested = false;
    var detailReads = 0;
    var requests = 0;
    final container = setup((r) async {
      if (r.url.path == '/board/select') {
        return result({
          'total': 1,
          'results': [post],
        });
      }
      if (r.url.path == '/board/select/10') {
        detailReads++;
        return result(post);
      }
      if (r.url.path == '/team_match/posts') {
        return result({
          'can_request': true,
          'results': [
            {...post, 'status': requested ? 'requested' : 'none'},
          ],
        });
      }
      if (r.url.path == '/team_match/request') {
        requests++;
        expect(jsonDecode(r.body), {
          'c_id_seq': 'member_01',
          'bulletin_seq': 10,
          'member_ids': ['member_01'],
        });
        requested = true;
        return result({'result': 'OK'}, 201);
      }
      if (r.url.path == '/team_match/lineup-options') {
        return result({
          'required_count': 1,
          'results': [
            {'c_id_seq': 'member_01', 'c_name': '회원'},
          ],
        });
      }
      return result({'results': []});
    });
    await tester.pumpWidget(app(container));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '매칭신청'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    await tester.tap(find.text('선택 완료'));
    await tester.pumpAndSettle();
    expect(requests, 1);
    expect(detailReads, 0);
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '신청 완료'))
          .onPressed,
      isNull,
    );
    expect(find.text('신청 목록'), findsNothing);
  });
  for (final decision in ['accept', 'reject']) {
    testWidgets('작성 팀장의 신청 목록에서 $decision 결정과 재조회', (tester) async {
      tester.view.physicalSize = const Size(800, 1100);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      var status = 'requested';
      final ownPost = {...post, 'c_id_seq': 'member_01'};
      final container = setup((r) async {
        if (r.url.path == '/board/select') {
          return result({
            'total': 1,
            'results': [ownPost],
          });
        }
        if (r.url.path == '/board/select/10') return result(ownPost);
        if (r.url.path == '/match/reservation/8') {
          return result({
            'g_name': '경기장',
            'r_date': '2026-11-01',
            'rs_time': '16:00',
            're_time': '18:00',
            'r_check': status == 'accepted',
          });
        }
        if (r.url.path == '/team_match/requests/10') {
          expect(r.url.queryParameters['c_id_seq'], 'member_01');
          return result({
            'post': {'t_id': 1, 't_name': '우리 팀'},
            'results': [
              {
                'comment_seq': 7,
                'c_id_seq': 'other_01',
                't_id': 2,
                't_name': '신청 팀',
                'status': status,
              },
            ],
          });
        }
        if (r.url.path == '/team_match/$decision') {
          expect(jsonDecode(r.body), {
            'c_id_seq': 'member_01',
            'bulletin_seq': 10,
            'comment_seq': 7,
          });
          status = decision == 'accept' ? 'accepted' : 'rejected';
          return result({'result': 'OK'});
        }
        return result({'results': []});
      });
      await tester.pumpWidget(app(container));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, '신청 목록'));
      await tester.pumpAndSettle();
      expect(find.text('신청 팀'), findsOneWidget);
      final action = decision == 'accept'
          ? find.widgetWithText(FilledButton, '승인')
          : find.widgetWithText(TextButton, '거절');
      await tester.ensureVisible(action);
      await tester.tap(action);
      await tester.pumpAndSettle();
      await tester.tap(find.text('확인'));
      await tester.pumpAndSettle();
      expect(status, decision == 'accept' ? 'accepted' : 'rejected');
      expect(find.text(decision == 'accept' ? '수락됨' : '거절됨'), findsOneWidget);
      await tester.tap(find.byTooltip('신청 목록 닫기'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, '신청 목록'));
      await tester.pumpAndSettle();
      expect(find.text(decision == 'accept' ? '수락됨' : '거절됨'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('팀장이 아닌 회원은 목록에서 매칭을 신청할 수 없음', (tester) async {
    final container = setup(
      (r) async => result(
        r.url.path == '/board/select'
            ? {
                'total': 1,
                'results': [post],
              }
            : {
                'can_request': false,
                'results': [post],
              },
      ),
    );
    await tester.pumpWidget(app(container));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '매칭신청'))
          .onPressed,
      isNull,
    );
  });
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
