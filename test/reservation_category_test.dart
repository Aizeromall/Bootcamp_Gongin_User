// 작업자 : 최현준
// 최초 작업 일 : 2026-10-28
import 'dart:convert';

import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/view/history/reservation_detail_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  // DB의 VARCHAR 분류 값이 예약 상세 화면에도 그대로 반영되는지 검증합니다.
  for (final entry in {'1': '실력 매칭', '2': '구장 전체 대여'}.entries) {
    testWidgets('예약 분류 문자열 ${entry.key} 표시', (tester) async {
      final api = MemberApi(
        client: MockClient(
          (request) async => http.Response.bytes(
            utf8.encode(
              jsonEncode({
                'c_id_seq': 'member_01',
                'reservation_category': entry.key,
                'g_name': '테스트 구장',
                'r_date': '2026-10-29',
                'rs_time': '10:00',
                're_time': '12:00',
                'is_canceled': true,
                'cancel_reason': '가상 테스트',
              }),
            ),
            200,
          ),
        ),
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
          child: const MaterialApp(home: ReservationDetailPage(seq: 7)),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text(entry.value), findsOneWidget);
    });
  }
}
// 최종 수정 일 : 2026-10-28
