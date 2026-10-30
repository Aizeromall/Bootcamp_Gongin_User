// 작업자 : 최현준
// 최초 작업 일 : 2026-10-30
import 'dart:convert';

import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/view/account/account_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  testWidgets('회원 종목 경기 스탯을 합산하고 다른 회원 기록을 제외한다', (tester) async {
    final api = MemberApi(
      client: MockClient((request) async {
        final data = request.url.path.startsWith('/rating/')
            ? {'tier': '비기너 1', 'total_matches': 2}
            : {
                'results': [
                  {
                    'c_id_seq': 'member_01',
                    'e_code': 'SOCCER',
                    'c_r_r_statcode': 'G:2,A:1',
                  },
                  {
                    'c_id_seq': 'member_01',
                    'e_code': 'SOCCER',
                    'c_r_r_statcode': 'G:1,A:3',
                  },
                  {
                    'c_id_seq': 'other_01',
                    'e_code': 'SOCCER',
                    'c_r_r_statcode': 'G:99',
                  },
                ],
              };
        return http.Response.bytes(utf8.encode(jsonEncode(data)), 200);
      }),
    );
    final container = ProviderContainer(
      overrides: [memberApiProvider.overrideWithValue(api)],
    );
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'member',
      'c_name': '회원',
      'preferred_stocks': [1],
    });
    addTearDown(() {
      container.dispose();
      api.client.close();
    });
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: Scaffold(
            body: AccountPage(onReservations: () {}, onTeams: () {}),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('골 3'), findsOneWidget);
    expect(find.text('어시스트 4'), findsOneWidget);
    expect(find.textContaining('승률'), findsNothing);
    expect(find.textContaining('일부 기록'), findsOneWidget);
  });
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
