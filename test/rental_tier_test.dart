// 작업자 : 최현준
// 최초 작업 일 : 2026-10-30
import 'dart:convert';

import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/view/account/account_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/ground/rental_availability_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/reservation/reservation_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  testWidgets('종목별 티어와 판수를 조회하고 대관 불가능 시간은 숨긴다', (tester) async {
    final api = MemberApi(
      client: MockClient((request) async {
        final path = request.url.path;
        final Object data = path.startsWith('/rating/summary/')
            ? {
                'tier': path.endsWith('01') ? '비기너 1' : '루키 1',
                'total_matches': 3,
              }
            : path == '/ground'
            ? {
                'results': [
                  {
                    'g_code': 1,
                    'g_name': '테스트 구장',
                    'g_address': '서울',
                    'g_information': '종목: 축구',
                  },
                ],
              }
            : {
                'slots': [
                  {
                    'rs_time': '08:00',
                    're_time': '10:00',
                    'is_available': true,
                  },
                  {
                    'rs_time': '10:00',
                    're_time': '12:00',
                    'is_available': false,
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
      'preferred_stocks': [1, 2],
    });
    addTearDown(() {
      container.dispose();
      api.client.close();
    });
    Widget wrap(Widget child) => UncontrolledProviderScope(
      container: container,
      child: MaterialApp(home: child),
    );
    await tester.pumpWidget(
      wrap(
        Scaffold(
          body: AccountPage(onReservations: () {}, onTeams: () {}),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('비기너 1'), findsOneWidget);
    expect(find.textContaining('경기 3회'), findsOneWidget);
    await tester.drag(find.byType(PageView), const Offset(-500, 0));
    await tester.pumpAndSettle();
    expect(find.text('루키 1'), findsOneWidget);
    await tester.pumpWidget(wrap(const RentalAvailabilityPage()));
    await tester.pumpAndSettle();
    expect(find.text('대관 시간을 선택해 주세요.'), findsOneWidget);
    expect(find.text('테스트 구장'), findsNothing);
    final tomorrow = DateTime.now().add(const Duration(days: 1));
    await tester.tap(find.byIcon(Icons.calendar_month));
    await tester.pumpAndSettle();
    if (tomorrow.month != DateTime.now().month) {
      await tester.tap(find.byTooltip('Next month'));
      await tester.pumpAndSettle();
    }
    await tester.tap(find.text('${tomorrow.day}').last);
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('rental-time-10')));
    await tester.pumpAndSettle();
    expect(find.text('선택한 시간에 대관 가능한 구장이 없습니다.'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('rental-time-8')));
    await tester.pumpAndSettle();
    expect(find.text('테스트 구장'), findsOneWidget);
    await tester.tap(find.text('테스트 구장'));
    await tester.pumpAndSettle();
    final page = tester.widget<ReservationPage>(find.byType(ReservationPage));
    expect(page.initialTime, '08:00');
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '결제 수단 선택'))
          .onPressed,
      isNotNull,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('선택 시간이 재조회 중 또는 예약 불가면 결제 버튼을 차단한다', (tester) async {
    final api = MemberApi(
      client: MockClient(
        (_) async => http.Response(
          '{"slots":[{"rs_time":"10:00","re_time":"12:00","is_available":false}]}',
          200,
        ),
      ),
    );
    final container = ProviderContainer(
      overrides: [memberApiProvider.overrideWithValue(api)],
    );
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'member',
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
          home: ReservationPage(
            ground: const {'g_code': 1, 'g_name': '구장'},
            rental: true,
            initialDate: DateTime.now().add(const Duration(days: 1)),
            initialTime: '10:00',
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '결제 수단 선택'))
          .onPressed,
      isNull,
    );
    expect(find.text('예약 불가'), findsOneWidget);
  });
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
