// 작업자 : 최현준
// 최초 작업 일 : 2026-10-30
import 'dart:convert';

import 'package:bootcamp_project_gongin_admin_app/view/shared/ground_price.dart';
import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/view/ground/ground_detail_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('개인 이용료는 인원으로 나누고 원 단위 반올림한다', () {
    expect(individualGroundPrice(60000, 12), 5000);
    expect(individualGroundPrice('100', '8'), 13);
    expect(individualGroundPrice(0, 4), 0);
  });
  test('금액 또는 수용 인원이 유효하지 않으면 임의 금액을 표시하지 않는다', () {
    expect(individualGroundPrice(null, 4), isNull);
    expect(individualGroundPrice(100, 0), isNull);
    expect(individualGroundPrice(-1, 4), isNull);
    expect(individualGroundPrice('NaN', 4), isNull);
  });
  testWidgets('구장 상세에서 개인 예상 금액과 전체 대여 금액을 구분한다', (tester) async {
    final api = MemberApi(
      client: MockClient(
        (_) async => http.Response.bytes(
          utf8.encode(
            '{"g_name":"구장","g_address":"서울","g_num":12,"g_price":60000}',
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
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: GroundDetailPage(code: '1')),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('5000원'), findsOneWidget);
    expect(find.text('전체 대여 60000원'), findsOneWidget);
  });
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
