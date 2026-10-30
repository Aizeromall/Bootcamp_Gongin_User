// 2026-10-30
// 작업자 : 김병재
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:bootcamp_project_gongin_admin_app/view/history/history_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/team/team_page.dart';

http.Response response(Object data, [int code = 200]) =>
    http.Response.bytes(utf8.encode(jsonEncode(data)), code);

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 축구(member_01)는 팀장, 농구(member_02)는 팀 없음 + 가입 대기 1건인 계정입니다.
Map<String, dynamic> myTeams() => {
  'results': [
    {
      'c_id_seq': 'member_01',
      'sport': 1,
      'team': {
        't_id': 7,
        't_name': 'FC 망원',
        'member_count': 2,
        'captain_id': 'member_01',
        'captain_name': '회원',
        'tier': '아마추어 2',
        'is_captain': true,
      },
      'pending': [],
    },
    {
      'c_id_seq': 'member_02',
      'sport': 2,
      'team': null,
      'pending': [
        {'t_id': 21, 't_name': '합정 리바운드'},
      ],
    },
  ],
};

void main() {
  testWidgets('종목별 소속팀 카드·팀장 화면·미가입 종목 팀 목록과 가입 신청', (tester) async {
    tester.view.physicalSize = const Size(500, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final posts = <String, Map>{};
    final client = MockClient((r) async {
      if (r.method == 'POST') {
        posts[r.url.path] = jsonDecode(r.body) as Map;
        return response({'result': 'OK'});
      }
      return switch (r.url.path) {
        '/my_team' => response(myTeams()),
        '/my_team/members/7' => response({
          'results': [
            {
              'c_id_seq': 'member_01',
              'c_name': '회원',
              'tier': '아마추어 2',
              'c_position': 'FW',
              'is_captain': true,
              'is_me': true,
            },
            {
              'c_id_seq': 'kim_01',
              'c_name': '김선수',
              'tier': '비기너 3',
              'c_position': 'GK',
            },
          ],
        }),
        '/team/applications/7' => response({
          'results': [
            {'c_id_seq': 'lee_01', 'c_name': '이서준', 'tr_state': '대기'},
            {'c_id_seq': 'old_01', 'c_name': '처리됨', 'tr_state': '승인'},
          ],
        }),
        // 개설자 ID 끝자리로 종목을 판단합니다: 21·22는 농구, 30은 야구 팀.
        '/team/select' => response({
          'total': 3,
          'results': [
            {'t_id': 21, 't_name': '합정 리바운드', 'creator_id': 'a_02'},
            {'t_id': 22, 't_name': '상암 덩크', 'creator_id': 'b_02'},
            {'t_id': 30, 't_name': '야구팀', 'creator_id': 'c_03'},
          ],
        }),
        _ => response({'results': []}),
      };
    });
    final container = ProviderContainer(
      overrides: [
        memberApiProvider.overrideWithValue(MemberApi(client: client)),
      ],
    );
    addTearDown(() {
      container.dispose();
      client.close();
    });
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'member',
      'c_name': '회원',
      'member_ids': ['member_01', 'member_02'],
      'preferred_stocks': [1, 2],
      'access_token': 'jwt',
    });
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: TeamPage())),
      ),
    );
    await tester.pumpAndSettle();

    // 팀장 화면: 팀 카드·등급·팀장 버튼·대기 신청만·팀원 목록
    expect(find.text('FC 망원'), findsNWidgets(2));
    expect(find.text('등급 아마추어 2'), findsOneWidget);
    for (final label in ['팀원 모집', '경기 매칭', '팀 채팅']) {
      expect(find.text(label), findsOneWidget);
    }
    expect(find.text('가입 신청 1건'), findsOneWidget);
    expect(find.text('처리됨'), findsNothing);
    expect(find.text('팀원 2명'), findsOneWidget);
    expect(find.text('비기너 3 · GK'), findsOneWidget);
    await tester.tap(find.text('승인'));
    await tester.pumpAndSettle();
    expect(posts['/team/approve/7'], {
      'c_id_seq': 'member_01',
      'applicant_id': 'lee_01',
    });

    // 팀이 없는 농구: 농구 팀만, 대기 중인 팀은 '신청 대기', 가입 신청은 농구 회원 ID로
    await tester.tap(find.text('+ 가입/개설'));
    await tester.pumpAndSettle();
    expect(find.text('농구 소속 팀이 없습니다'), findsOneWidget);
    expect(find.text('야구팀'), findsNothing);
    expect(find.text('신청 대기'), findsOneWidget);
    expect(find.text('팀원 모집'), findsNothing);
    await tester.tap(find.text('가입 신청'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('확인'));
    await tester.pumpAndSettle();
    expect(posts['/team/apply/22'], {'c_id_seq': 'member_02'});
  });

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 종목 Dropdown 제거: 예약내역은 모든 종목을 합쳐 최신 경기순으로, 종목 배지는 각 예약의 종목으로 표시합니다.
  testWidgets('예약내역은 가입한 모든 종목을 합쳐 표시', (tester) async {
    final client = MockClient((r) async {
      if (r.url.path.contains('/payment/')) return response({'results': []});
      final soccer = r.url.path.endsWith('member_01');
      return response({
        'results': [
          {
            'r_seq': soccer ? 1 : 2,
            'g_name': soccer ? '축구 구장' : '농구 구장',
            'r_date': soccer ? '2026-10-01' : '2026-10-20',
            'rs_time': '08:00',
            're_time': '10:00',
            'is_paid': true,
          },
        ],
      });
    });
    final container = ProviderContainer(
      overrides: [
        memberApiProvider.overrideWithValue(MemberApi(client: client)),
      ],
    );
    addTearDown(() {
      container.dispose();
      client.close();
    });
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'member',
      'member_ids': ['member_01', 'member_02'],
      'preferred_stocks': [1, 2],
    });
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: HistoryPage())),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('축구 구장'), findsOneWidget);
    expect(find.text('농구 구장'), findsOneWidget);
    expect(find.text('농구'), findsOneWidget);
    expect(
      tester.getTopLeft(find.text('농구 구장')).dy,
      lessThan(tester.getTopLeft(find.text('축구 구장')).dy),
    );
  });
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
