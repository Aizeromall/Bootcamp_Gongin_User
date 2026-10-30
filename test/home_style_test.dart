// 2026-10-27
// 작업자 : 양태건
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:bootcamp_project_gongin_admin_app/app.dart';
import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';

void main() {
  // 수정 일 : 2026-10-27 / 작업자 : 양태건
  // 좁은 화면·바로가기 경로·실제 결과 수를 확인하며 필요 시 검토용 PNG를 생성합니다.
  testWidgets('목업 홈의 반응형 배치·게시판 바로가기·하단 메뉴', (tester) async {
    final font = FontLoader('IBM Plex Sans KR')
      ..addFont(rootBundle.load('assets/fonts/IBMPlexSansKR-Regular.ttf'));
    await font.load();
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
    const preview = String.fromEnvironment('HOME_PREVIEW_PATH');
    // 시각 검토용 PNG에만 호스트의 이모지 폰트를 사용합니다. 앱 번들에는 복사하지 않습니다.
    if (preview.isNotEmpty) {
      await tester.runAsync(() async {
        final emoji = File('/System/Library/Fonts/Apple Color Emoji.ttc');
        if (await emoji.exists()) {
          final loader = FontLoader('Apple Color Emoji')
            ..addFont(emoji.readAsBytes().then(ByteData.sublistView));
          await loader.load();
        }
      });
    }
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final calls = <Uri>[];
    final api = MemberApi(
      client: MockClient((request) async {
        calls.add(request.url);
        return http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'total': 0,
              'results': request.url.path == '/ground'
                  ? [
                      for (final entry in [
                        '마포 하늘풋살파크 A구장',
                        '고양 킨텍스 스포츠필드',
                        '영등포 더풋볼 B구장',
                        '성수 루프탑 풋살 1구장',
                      ])
                        {
                          'g_code': entry,
                          'g_name': entry,
                          'g_address': '서울특별시 마포구 하늘공원로 108',
                          'g_information': '종목: 축구',
                          'g_time': '08:00~22:00',
                          'g_num': 12,
                          'g_price': 60000,
                        },
                    ]
                  : [],
            }),
          ),
          200,
        );
      }),
    );
    final container = ProviderContainer(
      overrides: [memberApiProvider.overrideWithValue(api)],
    );
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'member',
      'c_name': '김민준',
      'preferred_stocks': [1],
    });
    addTearDown(() {
      container.dispose();
      api.client.close();
    });
    const boundaryKey = ValueKey('homePreview');
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const RepaintBoundary(key: boundaryKey, child: MyApp()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('4개'), findsOneWidget);
    expect(find.text('운영시간 08:00~22:00'), findsWidgets);
    // 수정 일 : 2026-10-30 / 작업자 : 최현준
    // 구장 카드에 다음 경기 시간 또는 남은 시간이 없다는 안내가 표시됩니다.
    expect(
      find.textContaining('다음 경기 시간 ·').evaluate().isNotEmpty ||
          find.text('남은 경기 시간 없음').evaluate().isNotEmpty,
      isTrue,
    );
    expect(find.text('오늘 5개 매치'), findsNothing);
    expect(tester.takeException(), isNull);
    if (preview.isNotEmpty) {
      final boundary = tester.renderObject<RenderRepaintBoundary>(
        find.byKey(boundaryKey),
      );
      await tester.runAsync(() async {
        final image = await boundary.toImage(pixelRatio: 2);
        final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
        await File(preview).writeAsBytes(bytes!.buffer.asUint8List());
        image.dispose();
      });
    }
    tester.view.physicalSize = const Size(320, 740);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('팀 매치'));
    await tester.pumpAndSettle();
    expect(calls.last.path, '/board/select');
    expect(calls.last.queryParameters['board_category'], '매칭신청');
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.text('게시판'));
    await tester.pumpAndSettle();
    expect(calls.last.path, '/board/select');
    expect(calls.last.queryParameters.containsKey('board_category'), false);
    await tester.pageBack();
    await tester.pumpAndSettle();
    for (final destination in ['예약', '팀', '메시지', 'MY', '홈']) {
      await tester.tap(find.text(destination).last);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    }
  });
}
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
