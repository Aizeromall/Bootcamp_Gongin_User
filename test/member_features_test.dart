// 2026-10-27
// 작업자 : 양태건
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:bootcamp_project_gongin_admin_app/app.dart';
import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_features.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/chat_state.dart';
import 'package:bootcamp_project_gongin_admin_app/view/team/team_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/team/team_create_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/board/board_detail_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/board/board_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/chat/chat_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/announcement/announcement_page.dart';

http.Response response(Object data, [int code = 200]) =>
    http.Response.bytes(utf8.encode(jsonEncode(data)), code);
ProviderContainer containerFor(
  Future<http.Response> Function(http.Request) handler,
) {
  final api = MemberApi(client: MockClient(handler));
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
  return container;
}

Widget app(ProviderContainer container, Widget child) =>
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(home: Scaffold(body: child)),
    );

void main() {
  // 수정 일 : 2026-10-27 / 작업자 : 양태건
  test('PUT·인증 헤더와 비JSON 오류 처리', () async {
    final calls = <http.Request>[];
    final api = MemberApi(
      client: MockClient((r) async {
        calls.add(r);
        return r.url.path == '/error'
            ? http.Response('Internal Server Error', 500)
            : response({'result': 'OK'});
      }),
    );
    addTearDown(api.client.close);
    await api.request(
      '/board/update/7',
      method: 'PUT',
      body: {'board_title': '한글'},
      accessToken: 'sample',
    );
    expect(calls.single.method, 'PUT');
    expect(calls.single.headers['Authorization'], 'Bearer sample');
    expect(jsonDecode(calls.single.body)['board_title'], '한글');
    await expectLater(
      api.request('/error'),
      throwsA(isA<ApiException>().having((e) => e.statusCode, 'status', 500)),
    );
  });
  test('종목 변경과 로그아웃 시 채팅 토큰 폐기', () {
    final container = containerFor((r) async => response({'results': []}));
    container.read(chatTokenProvider.notifier).setToken('token');
    expect(container.read(chatTokenProvider), 'token');
    container.read(sportProvider.notifier).select(2);
    expect(container.read(chatTokenProvider), isNull);
    container.read(chatTokenProvider.notifier).setToken('another');
    container.read(sessionProvider.notifier).signOut();
    expect(container.read(chatTokenProvider), isNull);
  });
  test('늦은 이전 회원 응답이 현재 회원 조회를 덮어쓰지 않음', () async {
    final first = Completer<http.Response>();
    var count = 0;
    final container = containerFor((r) async {
      count++;
      return count == 1
          ? first.future
          : response({
              'results': [
                {'name': '현재 회원'},
              ],
            });
    });
    final query = apiQuery('/team/select');
    final subscription = container.listen(
      apiDocumentProvider(query),
      (_, _) {},
    );
    addTearDown(subscription.close);
    await Future<void>.delayed(Duration.zero);
    container.read(sportProvider.notifier).select(2);
    final current = await container.read(apiDocumentProvider(query).future);
    expect(apiRows(current).single['name'], '현재 회원');
    first.complete(
      response({
        'results': [
          {'name': '이전 회원'},
        ],
      }),
    );
    await Future<void>.delayed(Duration.zero);
    expect(
      apiRows(container.read(apiDocumentProvider(query)).requireValue)
          .single['name'],
      '현재 회원',
    );
  });
  testWidgets('팀 개설 실패 입력 보존·재시도와 회원 FK', (tester) async {
    var attempts = 0;
    final container = containerFor((r) async {
      if (r.method == 'POST') {
        expect(r.url.path, '/team/create');
        expect(jsonDecode(r.body), {'t_name': '초록 팀', 'c_id_seq': 'member_01'});
        return ++attempts == 1
            ? response({'detail': '중복된 팀명입니다.'}, 409)
            : response({'result': 'OK'}, 201);
      }
      return response({'results': [], 'total': 0});
    });
    await tester.pumpWidget(app(container, const TeamPage()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('팀 개설'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('teamName')), '초록 팀');
    await tester.tap(find.text('팀 만들기'));
    await tester.pumpAndSettle();
    expect(find.byType(TeamCreatePage), findsOneWidget);
    expect(find.text('초록 팀'), findsOneWidget);
    await tester.tap(find.text('팀 만들기'));
    await tester.pumpAndSettle();
    expect(attempts, 2);
    expect(find.byType(TeamCreatePage), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets('최초 댓글은 부모 없이, 대댓글은 실제 부모 번호로 등록', (tester) async {
    final sent = <Map>[];
    final container = containerFor((r) async {
      if (r.method == 'POST') {
        sent.add(jsonDecode(r.body) as Map);
        return response({'result': 'OK'}, 201);
      }
      if (r.url.path.contains('/comment/')) {
        return response({
          'results': [
            {
              'comment_seq': 4,
              'c_id_seq': 'other_01',
              'c_name': '다른 회원',
              'depth': 0,
              'comment_content': '부모 댓글',
              'comment_delete_state': false,
            },
          ],
        });
      }
      return response({
        'board_title': '테스트 글',
        'board_content': '내용',
        'board_category': '자유',
        'event_category': '축구',
        'c_id_seq': 'other_01',
      });
    });
    await tester.pumpWidget(app(container, const BoardDetailPage(seq: 3)));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const ValueKey('boardCommentInput')),
      '최초 댓글',
    );
    await tester.tap(find.text('등록'));
    await tester.pumpAndSettle();
    expect(sent.first, {'comment_content': '최초 댓글', 'c_id_seq': 'member_01'});
    await tester.tap(find.text('답글'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), '대댓글');
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();
    expect(sent.last['reply_to_comment_seq'], 4);
    expect(sent.last.containsKey('depth'), false);
  });
  testWidgets('매칭 성사 후 댓글·대댓글 작성 버튼 차단', (tester) async {
    // 수정 일 : 2026-10-28 / 작업자 : 양태건
    // 연결 경기 카드 아래의 댓글 버튼까지 검증합니다.
    tester.view.physicalSize = const Size(800, 1200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final container = containerFor((r) async {
      if (r.url.path.contains('/comment/')) {
        return response({
          'results': [
            {
              'comment_seq': 4,
              'c_id_seq': 'other_01',
              'depth': 1,
              'comment_content': '댓글',
            },
          ],
        });
      }
      if (r.url.path.startsWith('/match/')) return response({'r_check': true});
      return response({
        'board_title': '매칭',
        'board_content': '[예약번호:8]\n매칭 내용',
        'board_category': '매칭신청',
        'event_category': '축구',
        'c_id_seq': 'other_01',
      });
    });
    await tester.pumpWidget(app(container, const BoardDetailPage(seq: 5)));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<TextField>(find.byKey(const ValueKey('boardCommentInput')))
          .enabled,
      false,
    );
    expect(
      tester
          .widget<TextButton>(find.widgetWithText(TextButton, '답글'))
          .onPressed,
      isNull,
    );
    expect(find.text('매칭이 성사되어 댓글 작성이 종료되었습니다.'), findsOneWidget);
  });
  testWidgets('채팅 로그인·인증 헤더·방 목록 조회', (tester) async {
    final calls = <http.Request>[];
    final container = containerFor((r) async {
      calls.add(r);
      if (r.url.path == '/chat/token') {
        expect(jsonDecode(r.body), {
          'c_id_seq': 'member_01',
          'c_pw': 'password123',
        });
        return response({'access_token': 'test-token'});
      }
      expect(r.headers['Authorization'], 'Bearer test-token');
      return response({'results': []});
    });
    await tester.pumpWidget(app(container, const ChatPage()));
    await tester.enterText(find.byType(TextField), 'password123');
    await tester.tap(find.text('채팅 로그인'));
    await tester.pumpAndSettle();
    expect(find.text('참여 중인 채팅방이 없습니다.'), findsOneWidget);
    expect(calls.last.url.path, '/chat/rooms');
    expect(calls.last.url.queryParameters['limit'], '20');
    expect(find.text('password123'), findsNothing);
  });
  testWidgets('공지 분류는 서버 목록을 사용하고 실제 내용 표시', (tester) async {
    final container = containerFor(
      (r) async => r.url.path.endsWith('categories')
          ? response({
              'results': ['이벤트'],
            })
          : response({
              'results': [
                {
                  'a_title': '새 소식',
                  'a_detail': '운영 안내',
                  'a_classify': '이벤트',
                  'a_date': '2026-10-27',
                },
              ],
            }),
    );
    await tester.pumpWidget(app(container, const AnnouncementPage()));
    await tester.pumpAndSettle();
    await tester.tap(find.text('새 소식'));
    await tester.pumpAndSettle();
    expect(find.text('운영 안내'), findsOneWidget);
    expect(find.widgetWithText(ChoiceChip, '이벤트'), findsOneWidget);
  });
  testWidgets('로그아웃 시 열린 보호 화면을 닫음', (tester) async {
    final container = containerFor((r) async => response({'results': []}));
    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const MyApp()),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('공지사항'));
    await tester.pumpAndSettle();
    expect(find.byType(AnnouncementPage), findsOneWidget);
    container.read(sessionProvider.notifier).signOut();
    await tester.pumpAndSettle();
    expect(find.byType(AnnouncementPage), findsNothing);
    expect(find.text('로그인'), findsWidgets);
  });
  testWidgets('390px 화면에서 새 탭 전환과 오류 재시도', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    var fail = true;
    final container = containerFor((r) async {
      if (r.url.path == '/team/select' && fail) {
        fail = false;
        return response({'detail': '잠시 후 다시 시도해 주세요.'}, 500);
      }
      return response({'results': [], 'total': 0});
    });
    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const MyApp()),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('팀'));
    await tester.pumpAndSettle();
    expect(find.text('다시 시도'), findsOneWidget);
    await tester.tap(find.text('다시 시도'));
    await tester.pumpAndSettle();
    expect(find.text('아직 표시할 내역이 없습니다.'), findsOneWidget);
    for (final name in ['메시지', 'MY', '홈']) {
      await tester.tap(find.text(name));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    }
  });
  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  // 분류별 작성 폼 초기값·전송값·등록 후 목록 갱신을 실제 DB 없이 검증합니다.
  for (final category in ['팀원모집', '매칭신청', '후기', '자유', '전체']) {
    testWidgets('$category에서 작성한 글의 분류와 목록 표시', (tester) async {
      tester.view.physicalSize = const Size(800, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final expected = category == '전체' ? '자유' : category;
      final posts = <Map<String, dynamic>>[];
      final container = containerFor((request) async {
        if (request.method == 'POST') {
          expect(request.url.path, '/board/insert');
          final body = Map<String, dynamic>.from(
            jsonDecode(request.body) as Map,
          );
          expect(body['board_category'], expected);
          expect(body['event_category'], '축구');
          posts.add({
            ...body,
            'bulletin_seq': 10,
            'c_name': '회원',
            'board_views': 0,
          });
          return response({'result': 'OK', 'bulletin_seq': 10}, 201);
        }
        final filter = request.url.queryParameters['board_category'];
        final rows = posts
            .where((post) => filter == null || post['board_category'] == filter)
            .toList();
        return response({'results': rows, 'total': rows.length});
      });
      // 팀 매치 진입과 동일한 initialCategory 경로도 함께 확인합니다.
      await tester.pumpWidget(
        app(
          container,
          BoardPage(initialCategory: category == '매칭신청' ? category : '전체'),
        ),
      );
      await tester.pumpAndSettle();
      if (category != '매칭신청') {
        await tester.tap(find.widgetWithText(ChoiceChip, category));
        await tester.pumpAndSettle();
      }
      await tester.tap(find.text('글쓰기'));
      await tester.pumpAndSettle();
      final fields = tester
          .widgetList<DropdownButtonFormField<String>>(
            find.byType(DropdownButtonFormField<String>),
          )
          .toList();
      expect(fields.last.initialValue, expected);
      await tester.enterText(
        find.byType(TextFormField).at(0),
        '$expected 등록 확인',
      );
      await tester.enterText(find.byType(TextFormField).at(1), '카테고리 검증 내용');
      await tester.tap(find.text('저장'));
      await tester.pumpAndSettle();
      expect(posts, hasLength(1));
      expect(find.text('$expected 등록 확인'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
