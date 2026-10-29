// 2026-10-28
// 작업자 : 양태건
import 'dart:convert';

import 'package:bootcamp_project_gongin_admin_app/view/board/board_recruitment_card.dart';
import 'package:bootcamp_project_gongin_admin_app/view/board/board_detail_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'member_screens_test.dart' as h;

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// HTTP Mock으로만 신청 대기·승인·거절·실패 후 재시도를 검증합니다.
void main() {
  testWidgets('모집 신청은 승인 대기로 바뀌며 중복 버튼을 비활성화', (tester) async {
    var pending = false;
    int calls = 0;
    int detailReads = 0;
    final container = h.setup((request) async {
      if (request.method == 'POST') {
        expect(request.url.path, '/team/apply/7');
        expect(jsonDecode(request.body), {
          'c_id_seq': 'member_01',
          'bulletin_seq': 10,
        });
        calls++;
        pending = true;
        return h.response({'tr_state': '대기'}, 201);
      }
      if (request.url.path == '/board/select/10') {
        detailReads++;
        return h.response({
          'bulletin_seq': 10,
          'board_category': '팀원모집',
          'event_category': '축구',
          'c_id_seq': 'captain_01',
          'c_name': '팀장',
          'board_title': '팀원을 모집합니다',
          'board_content': '함께 운동해요',
          'board_views': 1,
        });
      }
      if (request.url.path.startsWith('/board/comment/')) {
        return h.response({'results': []});
      }
      return h.response({
        'team': {'t_id': 7, 't_name': '우리 팀'},
        'can_manage': false,
        'can_apply': !pending,
        'my_state': pending ? '대기' : null,
        'results': [],
      });
    });
    await tester.pumpWidget(h.app(container, const BoardDetailPage(seq: 10)));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('신청하기'));
    await tester.tap(find.text('신청하기'));
    await tester.pumpAndSettle();
    expect(find.textContaining('팀장 승인 후'), findsOneWidget);
    await tester.tap(find.text('확인'));
    await tester.pumpAndSettle();
    expect(calls, 1);
    expect(detailReads, 1);
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, '신청 완료 · 승인 대기'),
          )
          .onPressed,
      isNull,
    );
  });
  for (final action in ['approve', 'reject']) {
    testWidgets('팀장이 $action 처리하고 실패하면 신청 정보를 유지', (tester) async {
      String state = '대기';
      int calls = 0;
      final container = h.setup((request) async {
        if (request.method == 'POST') {
          expect(request.url.path, '/team/$action/7');
          expect(jsonDecode(request.body), {
            'c_id_seq': 'member_01',
            'applicant_id': 'applicant_01',
          });
          calls++;
          if (calls == 1) {
            return h.response({'detail': '잠시 후 다시 시도해 주세요.'}, 409);
          }
          state = action == 'approve' ? '승인' : '거절';
          return h.response({'result': 'OK', 'tr_state': state});
        }
        return h.response({
          'team': {'t_id': 7, 't_name': '우리 팀'},
          'can_manage': true,
          'can_apply': false,
          'results': [
            {'c_name': '신청자', 'c_id_seq': 'applicant_01', 'tr_state': state},
          ],
        });
      });
      await tester.pumpWidget(
        h.app(
          container,
          const Scaffold(body: BoardRecruitmentCard(seq: 10, sport: '축구')),
        ),
      );
      await tester.pumpAndSettle();
      final label = action == 'approve' ? '승인' : '거절';
      for (var i = 0; i < 2; i++) {
        await tester.tap(find.text(label));
        await tester.pumpAndSettle();
        await tester.tap(find.text('확인'));
        await tester.pumpAndSettle();
        if (i == 0) expect(find.textContaining('잠시 후 다시 시도'), findsOneWidget);
      }
      expect(find.text('신청자 · $label'), findsOneWidget);
      expect(find.text('가입 신청 목록 · 0건 대기'), findsOneWidget);
    });
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
