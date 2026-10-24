// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:bootcamp_project_gongin_admin_app/app.dart';
import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:bootcamp_project_gongin_admin_app/view/payment/payment_page.dart';

void main() {
  testWidgets('결제 확인 후 예약 번호와 로그인 회원 FK를 서버에 전달', (tester) async {
    Map<String, dynamic>? sent;
    final api = MemberApi(
      client: MockClient((request) async {
        sent = Map<String, dynamic>.from(jsonDecode(request.body) as Map);
        return http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'p_num': '2_1',
              'p_amount': 5000,
              'p_date': '2026-10-25',
              'p_method': '카드 결제',
            }),
          ),
          201,
        );
      }),
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [memberApiProvider.overrideWithValue(api)],
        child: const MaterialApp(
          home: PaymentPage(
            rSeq: 1,
            memberId: 'member_01',
            groundName: '테스트 구장',
          ),
        ),
      ),
    );
    await tester.tap(find.text('결제 기록 저장'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('기록 저장'));
    await tester.pumpAndSettle();
    expect(sent, {'r_seq': 1, 'c_id_seq': 'member_01', 'p_method': '카드 결제'});
    expect(find.text('결제 기록이 저장되었어요'), findsOneWidget);
  });
  testWidgets('로그인 진입, 로그인 응답 종목 선택, 구장 조회와 문의 연결', (tester) async {
    final calls = <String>[];
    final client = MockClient((request) async {
      calls.add(request.url.path);
      final data = switch (request.url.path) {
        '/auth/login' => {
          'c_id': 'member',
          'c_name': '회원',
          'preferred_stocks': ['3'],
        },
        '/match/ground' => {'results': []},
        '/inquiry/list' => {'results': []},
        _ => {'results': []},
      };
      return http.Response.bytes(utf8.encode(jsonEncode(data)), 200);
    });
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          memberApiProvider.overrideWithValue(MemberApi(client: client)),
        ],
        child: const MyApp(),
      ),
    );
    expect(find.text('로그인'), findsOneWidget);
    await tester.enterText(find.byType(TextFormField).at(0), 'member');
    await tester.enterText(find.byType(TextFormField).at(1), 'password123');
    await tester.tap(find.text('로그인'));
    await tester.pumpAndSettle();
    expect(find.text('오늘은 어디서 뛸까요?'), findsOneWidget);
    expect(find.text('야구'), findsOneWidget);
    await tester.tap(find.text('문의'));
    await tester.pumpAndSettle();
    expect(find.text('무엇을 도와드릴까요?'), findsOneWidget);
    expect(
      calls,
      containsAll(['/auth/login', '/match/ground', '/inquiry/list']),
    );
  });
  test('서버 422 세부 오류를 사용자 메시지로 변환', () async {
    final api = MemberApi(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode({
            'detail': [
              {
                'loc': ['body', 'c_id_seq'],
                'msg': 'Field required',
              },
            ],
          }),
          422,
        ),
      ),
    );
    await expectLater(
      api.request('/match/payment', body: {}),
      throwsA(
        predicate((e) => '$e'.contains('c_id_seq: Field required (422)')),
      ),
    );
    api.client.close();
  });
}
// 최종 수정 일 : 2026-10-24
