// 2026-10-28
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
import 'package:bootcamp_project_gongin_admin_app/view/board/board_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/board/board_detail_page.dart';

http.Response jsonResponse(Object data, [int status = 200]) =>
    http.Response.bytes(utf8.encode(jsonEncode(data)), status);
ProviderContainer setup(Future<http.Response> Function(http.Request) handler) {
  final api = MemberApi(client: MockClient(handler));
  final container = ProviderContainer(
    overrides: [memberApiProvider.overrideWithValue(api)],
  );
  container.read(sessionProvider.notifier).signIn({
    'c_id': 'member',
    'c_name': '김민준',
    'preferred_stocks': [1, 4],
  });
  addTearDown(() {
    container.dispose();
    api.client.close();
  });
  return container;
}

Widget app(ProviderContainer container, Widget page) =>
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(home: page),
    );
const post = {
  'bulletin_seq': 10,
  'c_id_seq': 'owner_01',
  'c_name': '블루윙즈 팀장',
  'event_category': '축구',
  'board_category': '매칭신청',
  'board_title': '10/31(토) 16시 상대팀 구해요 · 하늘풋살파크',
  'board_content': '[예약번호:8]\n구장은 저희가 잡아뒀고 구장비는 반반이에요.\n즐겁게 함께 뛸 팀을 구합니다.',
  'board_date': '2026-10-28T16:40:00',
  'board_views': 118,
};
const reservation = {
  'r_seq': 8,
  'g_name': '마포 하늘풋살파크 A',
  'r_date': '2026-10-31',
  'rs_time': '16:00',
  're_time': '18:00',
  'r_check': false,
  'r_category': '1',
};
const match = {
  'bulletin_seq': 10,
  't_name': '상암 블루윙즈',
  't_rating': 1500,
  'status': 'none',
};
Future<void> preview(WidgetTester tester, String name) async {
  const prefix = String.fromEnvironment('BOARD_PREVIEW_PATH');
  if (prefix.isEmpty) return;
  await tester.runAsync(() async {
    final boundary = tester.renderObject<RenderRepaintBoundary>(
      find.byKey(const ValueKey('boardPreview')),
    );
    final image = await boundary.toImage(pixelRatio: 2);
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    await File('$prefix-$name.png').writeAsBytes(bytes!.buffer.asUint8List());
    image.dispose();
  });
}

void main() {
  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  testWidgets('종목·카테고리 조회와 상세 이동, 목업 시각 검토', (tester) async {
    final font = FontLoader('IBM Plex Sans KR')
      ..addFont(rootBundle.load('assets/fonts/IBMPlexSansKR-Regular.ttf'));
    await font.load();
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
    const previewPath = String.fromEnvironment('BOARD_PREVIEW_PATH');
    if (previewPath.isNotEmpty) {
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
    final container = setup((r) async {
      calls.add(r.url);
      if (r.url.path == '/board/select') {
        return jsonResponse({
          'total': 3,
          'results': [
            post,
            {
              ...post,
              'bulletin_seq': 11,
              'board_category': '팀원모집',
              'board_title': '상암 블루윙즈 신규 멤버 모집',
            },
            {
              ...post,
              'bulletin_seq': 12,
              'board_category': '후기',
              'board_title': '어제 매치 즐거웠습니다',
            },
          ].map((row) => {...row}..remove('board_content')).toList(),
        });
      }
      if (r.url.path == '/board/select/10') return jsonResponse(post);
      if (r.url.path.contains('/comment/')) {
        return jsonResponse({
          'results': [
            {
              'comment_seq': 1,
              'c_id_seq': 'member_01',
              'c_name': '반포빅맨',
              'comment_content': '구장 주차 가능한가요?',
              'depth': 0,
            },
            {
              'comment_seq': 2,
              'c_id_seq': 'owner_01',
              'c_name': '블루윙즈 팀장',
              'comment_content': '네 주차 가능합니다.',
              'depth': 1,
              'reply_to_comment_seq': 1,
            },
          ],
        });
      }
      if (r.url.path == '/match/reservation/8') {
        return jsonResponse(reservation);
      }
      if (r.url.path == '/team_match/posts') {
        return jsonResponse({
          'can_request': true,
          'results': [match],
        });
      }
      return jsonResponse({'results': []});
    });
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const RepaintBoundary(
          key: ValueKey('boardPreview'),
          child: MyApp(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final context = tester.element(find.byType(MyApp));
    // MaterialApp의 Navigator가 있는 하위 context를 사용합니다.
    final navigator = tester.state<NavigatorState>(find.byType(Navigator));
    navigator.push(MaterialPageRoute<void>(builder: (_) => const BoardPage()));
    await tester.pumpAndSettle();
    await preview(tester, 'list');
    expect(find.text('HOT 게시물'), findsNothing);
    await tester.tap(find.byKey(const ValueKey('boardSport4')));
    await tester.pumpAndSettle();
    expect(
      calls
          .lastWhere((uri) => uri.path == '/board/select')
          .queryParameters['event_category'],
      '배구',
    );
    expect(container.read(sportProvider), 1);
    await tester.tap(find.widgetWithText(ChoiceChip, '후기'));
    await tester.pumpAndSettle();
    expect(
      calls
          .lastWhere((uri) => uri.path == '/board/select')
          .queryParameters['board_category'],
      '후기',
    );
    await tester.tap(find.byKey(const ValueKey('boardSport1')));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ChoiceChip, '전체'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('${post['board_title']}'));
    await tester.pumpAndSettle();
    await preview(tester, 'detail');
    expect(find.text('등록'), findsOneWidget);
    expect(find.text('공감'), findsNothing);
    expect(tester.takeException(), isNull);
    expect(context.mounted, true);
  });
  testWidgets('하단 댓글 등록 실패 시 입력 보존, 성공 후 목록 갱신과 조회 수 보존', (tester) async {
    var detailReads = 0;
    var attempts = 0;
    final comments = <Map<String, dynamic>>[];
    final container = setup((r) async {
      if (r.url.path == '/board/select/10') {
        detailReads++;
        return jsonResponse({
          ...post,
          'board_category': '자유',
          'board_content': '본문',
        });
      }
      if (r.method == 'POST') {
        final body = jsonDecode(r.body);
        expect(body, {'c_id_seq': 'member_01', 'comment_content': '새 댓글'});
        if (++attempts == 1) {
          return jsonResponse({'detail': '잠시 후 다시 시도해 주세요.'}, 500);
        }
        comments.add({
          'comment_seq': 3,
          'c_id_seq': 'member_01',
          'c_name': '김민준',
          'comment_content': '새 댓글',
          'depth': 0,
        });
        return jsonResponse({'result': 'OK'}, 201);
      }
      return jsonResponse({'results': comments});
    });
    await tester.pumpWidget(app(container, const BoardDetailPage(seq: 10)));
    await tester.pumpAndSettle();
    final input = find.byKey(const ValueKey('boardCommentInput'));
    await tester.enterText(input, '새 댓글');
    await tester.tap(find.text('등록'));
    await tester.pumpAndSettle();
    expect(tester.widget<TextField>(input).controller!.text, '새 댓글');
    await tester.tap(find.text('등록'));
    await tester.pumpAndSettle();
    expect(tester.widget<TextField>(input).controller!.text, isEmpty);
    expect(find.text('새 댓글'), findsOneWidget);
    expect(detailReads, 1);
  });
  testWidgets('경기 카드 매칭 신청과 중복 신청 방지', (tester) async {
    var requested = false;
    final container = setup((r) async {
      if (r.url.path == '/board/select/10') return jsonResponse(post);
      if (r.url.path == '/match/reservation/8') {
        return jsonResponse(reservation);
      }
      if (r.url.path == '/team_match/posts') {
        return jsonResponse({
          'can_request': true,
          'results': [
            {...match, 'status': requested ? 'requested' : 'none'},
          ],
        });
      }
      if (r.url.path == '/team_match/request') {
        expect(jsonDecode(r.body), {
          'c_id_seq': 'member_01',
          'bulletin_seq': 10,
        });
        requested = true;
        return jsonResponse({'result': 'OK'}, 201);
      }
      return jsonResponse({'results': []});
    });
    tester.view.physicalSize = const Size(390, 1100);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(app(container, const BoardDetailPage(seq: 10)));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.widgetWithText(FilledButton, '매칭 신청'));
    await tester.tap(find.widgetWithText(FilledButton, '매칭 신청'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('확인'));
    await tester.pumpAndSettle();
    expect(requested, true);
    expect(
      tester
          .widget<FilledButton>(
            find.widgetWithText(FilledButton, '신청 완료 · 응답 대기'),
          )
          .onPressed,
      isNull,
    );
  });
  testWidgets('작성자의 매칭 수락 후 댓글·답글 입력 차단', (tester) async {
    var accepted = false;
    var detailReads = 0;
    final container = setup((r) async {
      if (r.url.path == '/board/select/10') {
        detailReads++;
        return jsonResponse({...post, 'c_id_seq': 'member_01'});
      }
      if (r.url.path == '/match/reservation/8') {
        return jsonResponse({...reservation, 'r_check': accepted});
      }
      if (r.url.path == '/team_match/requests/10') {
        return jsonResponse({
          'post': {...match, 't_id': 1},
          'results': [
            {
              'comment_seq': 7,
              'c_id_seq': 'other_01',
              't_id': 2,
              't_name': '상대 팀',
              'status': accepted ? 'accepted' : 'requested',
            },
          ],
        });
      }
      if (r.url.path == '/team_match/accept') {
        expect(jsonDecode(r.body), {
          'c_id_seq': 'member_01',
          'bulletin_seq': 10,
          'comment_seq': 7,
        });
        accepted = true;
        return jsonResponse({'result': 'OK'});
      }
      return jsonResponse({'results': []});
    });
    tester.view.physicalSize = const Size(390, 1100);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(app(container, const BoardDetailPage(seq: 10)));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.widgetWithText(FilledButton, '승인'));
    await tester.tap(find.widgetWithText(FilledButton, '승인'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('확인'));
    await tester.pumpAndSettle();
    expect(accepted, true);
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('boardCommentInput')))
          .enabled,
      false,
    );
    expect(detailReads, 1);
    expect(tester.takeException(), isNull);
  });
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
