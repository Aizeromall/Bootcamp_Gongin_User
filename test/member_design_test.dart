// 2026-10-28
// 작업자 : 양태건
import 'package:bootcamp_project_gongin_admin_app/app.dart';
import 'package:bootcamp_project_gongin_admin_app/view/account/account_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/ground/ground_detail_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/history/history_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'member_screens_test.dart' as h;

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 실제 앱 테마로 작은 화면·확대 글꼴·하단 동작과 Mock 데이터 표시를 검증합니다.
void main() {
  testWidgets('목업 스타일 MY·구장·예약 내역의 작은 화면과 하단 버튼', (tester) async {
    final font = FontLoader('IBM Plex Sans KR')
      ..addFont(rootBundle.load('assets/fonts/IBMPlexSansKR-Regular.ttf'));
    await font.load();
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
    final container = h.setup((request) async {
      if (request.url.path.startsWith('/ground/reservation/slots/')) {
        return h.response({'slots': []});
      }
      if (request.url.path == '/ground/1') {
        return h.response({
          'g_code': '1',
          'g_name': '마포 하늘풋살파크 A구장',
          'g_address': '서울특별시 마포구 하늘공원로 108',
          'g_num': 12,
          'g_time': '08:00~22:00',
          'g_price': 120000,
          'm_name': '박매니저',
          'g_information': '축구 · 풋살\n운동화와 개인 물병을 준비해 주세요.',
        });
      }
      if (request.url.path.startsWith('/match/reservation/customer/')) {
        return h.response({
          'results': [
            {
              'r_seq': 7,
              'g_name': '마포 하늘풋살파크 A구장',
              'r_date': '2026-10-30',
              'rs_time': '19:00',
              're_time': '21:00',
              'is_paid': true,
              'r_check': true,
            },
          ],
        });
      }
      if (request.url.path.startsWith('/match/payment/customer/')) {
        return h.response({
          'results': [
            {'r_seq': 7, 'p_num': 3, 'p_amount': 10000, 'p_method': '카드 결제'},
          ],
        });
      }
      return h.response({'results': []});
    });
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 844);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const MyApp()),
    );
    await tester.pumpAndSettle();
    final theme = tester.widget<MaterialApp>(find.byType(MaterialApp)).theme;
    Future<void> show(Widget page) async {
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            theme: theme,
            builder: (context, child) => RepaintBoundary(
              key: const ValueKey('memberPreview'),
              child: MediaQuery(
                data: MediaQuery.of(context)
                    .copyWith(textScaler: const TextScaler.linear(1.2)),
                child: child!,
              ),
            ),
            home: page,
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    await show(
      Scaffold(
        appBar: AppBar(title: const Text('MY')),
        body: AccountPage(onReservations: () {}, onTeams: () {}),
      ),
    );
    expect(find.text('김민준'), findsOneWidget);
    expect(find.text('축구'), findsOneWidget);
    await h.snapshot(tester, 'my-refined');
    await show(
      Scaffold(
        appBar: AppBar(title: const Text('예약 내역')),
        body: const HistoryPage(),
      ),
    );
    expect(find.text('마포 하늘풋살파크 A구장'), findsOneWidget);
    expect(find.textContaining('10000원'), findsOneWidget);
    await h.snapshot(tester, 'history-refined');
    await show(const GroundDetailPage(code: '1'));
    expect(find.text('120000원'), findsOneWidget);
    expect(find.text('실력 매칭 · 자리 예약').hitTestable(), findsOneWidget);
    await h.snapshot(tester, 'ground-refined');
    for (final size in [const Size(320, 640), const Size(390, 844)]) {
      tester.view.physicalSize = size;
      await tester.pumpAndSettle();
      expect(find.text('실력 매칭 · 자리 예약').hitTestable(), findsOneWidget);
      expect(find.text('구장 전체 대여').hitTestable(), findsOneWidget);
      expect(tester.takeException(), isNull);
    }
    await tester.tap(find.text('구장 전체 대여'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(AppBar, '구장 전체 대여'), findsOneWidget);
  });
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
