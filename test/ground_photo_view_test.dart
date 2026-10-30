// 작업자 : 최현준
// 최초 작업 일 : 2026-10-30
import 'dart:convert';

import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/view/ground/ground_detail_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  testWidgets('구장 사진 목록 오류 후 재시도하고 사진 경로를 연결한다', (tester) async {
    var attempts = 0;
    final calls = <String>[];
    final api = MemberApi(
      client: MockClient((request) async {
        calls.add(request.url.path);
        if (request.url.path == '/ground/2/photos') {
          attempts++;
          if (attempts == 1) return http.Response('{"detail":"error"}', 500);
          return http.Response(
            '{"results":[{"shoot_seq":12},{"shoot_seq":13}]}',
            200,
          );
        }
        return http.Response.bytes(
          utf8.encode(
            '{"g_name":"구장","g_address":"서울","g_num":12,"g_price":60000}',
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
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: GroundDetailPage(code: '2')),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('구장 사진을 불러오지 못했습니다.'), findsOneWidget);
    await tester.tap(find.text('다시 시도'));
    await tester.pumpAndSettle();
    final image = tester.widget<Image>(
      find.byKey(const ValueKey('ground-photo-12')),
    );
    expect(
      (image.image as NetworkImage).url,
      '${MemberApi.baseUrl}/ground/2/photos/12',
    );
    expect(calls.where((path) => path == '/ground/2/photos').length, 2);
    expect(find.byType(PageView), findsOneWidget);
    // 3초 자동 이동, 마지막 사진에서 처음으로 돌아감, 수동 이동을 확인합니다.
    final controller = tester
        .widget<PageView>(find.byType(PageView))
        .controller!;
    await tester.pump(const Duration(seconds: 3));
    await tester.pump(const Duration(milliseconds: 350));
    expect(controller.page, closeTo(1, 0.01));
    await tester.pump(const Duration(seconds: 3));
    await tester.pump();
    expect(controller.page, closeTo(0, 0.01));
    await tester.drag(find.byType(PageView), const Offset(-350, 0));
    await tester.pumpAndSettle();
    expect(controller.page, closeTo(1, 0.01));
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(seconds: 4));
    expect(tester.takeException(), isNull);
  });

  testWidgets('사진이 없는 구장은 빈 상태를 표시한다', (tester) async {
    final api = MemberApi(
      client: MockClient(
        (request) async => http.Response.bytes(
          utf8.encode(
            request.url.path.endsWith('/photos')
                ? '{"results":[]}'
                : '{"g_name":"구장","g_num":10,"g_price":10000}',
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
        child: const MaterialApp(home: GroundDetailPage(code: '2')),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('등록된 구장 사진이 없습니다.'), findsOneWidget);
  });
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
