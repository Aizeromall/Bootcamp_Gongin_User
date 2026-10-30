// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'package:bootcamp_project_gongin_admin_app/view/home/home_banner.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/banner_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('배너를 좌우로 밀어 이전·다음 사진을 볼 수 있음', (tester) async {
    final container = ProviderContainer(
      overrides: [
        bannerProvider.overrideWith((ref) async => [1, 2]),
      ],
    );
    addTearDown(container.dispose);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: HomeBanner())),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.fling(find.byType(HomeBanner), const Offset(-200, 0), 1000);
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byKey(const ValueKey('home-banner-2')), findsOneWidget);
    await tester.fling(find.byType(HomeBanner), const Offset(200, 0), 1000);
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byKey(const ValueKey('home-banner-1')), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('4초마다 다음 배너를 표시하고 마지막 다음은 처음으로 돌아감', (tester) async {
    final container = ProviderContainer(
      overrides: [
        bannerProvider.overrideWith((ref) async => [1, 2]),
      ],
    );
    addTearDown(container.dispose);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: HomeBanner())),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byKey(const ValueKey('home-banner-1')), findsOneWidget);
    await tester.pump(const Duration(seconds: 4));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byKey(const ValueKey('home-banner-2')), findsOneWidget);
    await tester.pump(const Duration(seconds: 4));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byKey(const ValueKey('home-banner-1')), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 8));
    expect(tester.takeException(), isNull);
  });

  testWidgets('활성 배너가 없으면 빈 상태를 표시', (tester) async {
    final container = ProviderContainer(
      overrides: [bannerProvider.overrideWith((ref) async => [])],
    );
    addTearDown(container.dispose);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: HomeBanner())),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('진행 중인 배너가 없습니다.'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
