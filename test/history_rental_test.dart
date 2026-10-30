// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'dart:convert';

import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/view/history/reservation_detail_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/history_state.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('대여 조회 실패를 빈 내역으로 숨기지 않음', () async {
    final api = MemberApi(
      client: MockClient((request) async {
        if (request.url.path.startsWith('/ground/')) {
          return http.Response('{"detail":"error"}', 500);
        }
        return http.Response('{"results":[]}', 200);
      }),
    );
    final container = ProviderContainer(
      overrides: [memberApiProvider.overrideWithValue(api)],
    );
    addTearDown(() {
      container.dispose();
      api.client.close();
    });
    await expectLater(
      container.read(
        historyProvider((id: 'member_01', canceled: false)).future,
      ),
      throwsA(anything),
    );
  });

  test('미성사 전체 대여와 개인 예약을 합치고 취소 사유를 유지', () async {
    final calls = <Uri>[];
    final api = MemberApi(
      client: MockClient((request) async {
        calls.add(request.url);
        final canceled = request.url.queryParameters['r_category'] == '2';
        final rental = request.url.path.startsWith('/ground/');
        final payment = request.url.path.startsWith('/match/payment/');
        final rows = payment
            ? [
                {'r_seq': 2, 'p_num': '3_2'},
              ]
            : [
                {
                  'r_seq': rental ? 2 : 1,
                  'r_check': false,
                  'reservation_category': rental ? '2' : '1',
                  if (canceled) 'cancel_reason': '기상 악화',
                },
              ];
        return http.Response.bytes(
          utf8.encode(jsonEncode({'results': rows})),
          200,
        );
      }),
    );
    final container = ProviderContainer(
      overrides: [memberApiProvider.overrideWithValue(api)],
    );
    addTearDown(() {
      container.dispose();
      api.client.close();
    });
    final active = await container.read(
      historyProvider((id: 'member_01', canceled: false)).future,
    );
    expect(active['results'], hasLength(2));
    expect(active['results'][1]['r_check'], isFalse);
    expect(active['results'][1]['p_num'], '3_2');
    final canceled = await container.read(
      historyProvider((id: 'member_01', canceled: true)).future,
    );
    expect(canceled['results'], hasLength(2));
    expect(canceled['results'][1]['cancel_reason'], '기상 악화');
    expect(
      calls
          .where((u) => u.path.startsWith('/ground/reservation/customer/'))
          .map((u) => u.queryParameters['r_category']),
      containsAll(['1', '2']),
    );
  });

  testWidgets('전체 대여 상세는 대여 상세 API를 사용', (tester) async {
    final paths = <String>[];
    final api = MemberApi(
      client: MockClient((request) async {
        paths.add(request.url.path);
        return http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'c_id_seq': 'member_01',
              'reservation_category': '2',
              'g_name': '전체 대여 구장',
              'r_date': '2100-01-01',
              'rs_time': '08:00',
              're_time': '10:00',
              'is_paid': false,
              'is_canceled': false,
              'r_check': false,
            }),
          ),
          200,
        );
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
      'c_id': 'member',
      'preferred_stocks': [1],
    });
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          home: ReservationDetailPage(seq: 2, rental: true),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(paths, contains('/ground/reservation/2'));
    expect(find.text('전체 대여 구장'), findsWidgets);
  });
}

// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
