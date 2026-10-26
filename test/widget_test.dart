// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:bootcamp_project_gongin_admin_app/app.dart';
import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/member_state.dart';
import 'package:bootcamp_project_gongin_admin_app/view/payment/payment_page.dart';

import 'package:bootcamp_project_gongin_admin_app/view/auth/register_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/history/history_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/ground/grounds_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/inquiry/inquiry_page.dart';

void main() {
  testWidgets('결제 확인 후 예약 번호와 로그인 회원 FK를 서버에 전달', (tester) async {
    Map<String, dynamic>? sent;
    final api = MemberApi(
      client: MockClient((request) async {
        sent = Map<String, dynamic>.from(jsonDecode(request.body) as Map);
        return http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'p_num': '2_1',
              'p_amount': 5000,
              'p_date': '2026-10-25',
              'p_method': '카드 결제',
            }),
          ),
          201,
        );
      }),
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [memberApiProvider.overrideWithValue(api)],
        child: const MaterialApp(
          home: PaymentPage(
            rSeq: 1,
            memberId: 'member_01',
            groundName: '테스트 구장',
          ),
        ),
      ),
    );
    await tester.tap(find.text('결제 기록 저장'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('기록 저장'));
    await tester.pumpAndSettle();
    expect(sent, {'r_seq': 1, 'c_id_seq': 'member_01', 'p_method': '카드 결제'});
    expect(find.text('결제 기록이 저장되었어요'), findsOneWidget);
  });
  testWidgets('로그인 진입, 로그인 응답 종목 선택, 구장 조회와 문의 연결', (tester) async {
    final calls = <String>[];
    final client = MockClient((request) async {
      calls.add(request.url.path);
      final data = switch (request.url.path) {
        '/auth/login' => {
          'c_id': 'member',
          'c_name': '회원',
          'preferred_stocks': ['3'],
        },
        // 중간 수정 작성자 - 신현진
        // 수정일 2026.10.26
        // 구장 조회 주소 변경 (/match/ground → /ground)
        '/ground' => {'results': []},
        '/inquiry/list' => {'results': []},
        _ => {'results': []},
      };
      return http.Response.bytes(utf8.encode(jsonEncode(data)), 200);
    });
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          memberApiProvider.overrideWithValue(MemberApi(client: client)),
        ],
        child: const MyApp(),
      ),
    );
    expect(find.text('로그인'), findsOneWidget);
    await tester.enterText(find.byType(TextFormField).at(0), 'member');
    await tester.enterText(find.byType(TextFormField).at(1), 'password123');
    await tester.tap(find.text('로그인'));
    await tester.pumpAndSettle();
    expect(find.text('오늘은 어디서 뛸까요?'), findsOneWidget);
    expect(find.text('야구'), findsOneWidget);
    await tester.tap(find.text('문의'));
    await tester.pumpAndSettle();
    expect(find.text('무엇을 도와드릴까요?'), findsOneWidget);
    expect(
      calls,
      containsAll(['/auth/login', '/ground', '/inquiry/list']),
    );
  });
  test('서버 422 세부 오류를 사용자 메시지로 변환', () async {
    final api = MemberApi(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode({
            'detail': [
              {
                'loc': ['body', 'c_id_seq'],
                'msg': 'Field required',
              },
            ],
          }),
          422,
        ),
      ),
    );
    await expectLater(
      api.request('/match/payment', body: {}),
      throwsA(
        predicate((e) => '$e'.contains('c_id_seq: Field required (422)')),
      ),
    );
    api.client.close();
  });
  // 디버그: 실제 DB 쓰기 없이 회원가입 payload와 조회 API 연결을 검증합니다.
  // 작업자 : 양태건 / 최종 수정일 : 2026-10-26
  testWidgets('회원가입 무소속 고정, 종목별 포지션 및 해제 후 초기화와 전송', (tester) async {
    tester.view.physicalSize = const Size(1200, 2600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    Map<String, dynamic>? sent;
    final api = MemberApi(
      client: MockClient((request) async {
        sent = jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response('{}', 201);
      }),
    );
    addTearDown(api.client.close);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [memberApiProvider.overrideWithValue(api)],
        child: MaterialApp(
          initialRoute: '/register',
          routes: {
            '/': (_) => const Scaffold(body: Text('로그인 화면')),
            '/register': (_) => const RegisterPage(),
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('선호 종목: 선택 없음'), findsOneWidget);
    expect(find.text('무소속'), findsOneWidget);
    expect(find.byType(TextFormField), findsNWidgets(5));
    final options = {
      '축구': ['FW', 'MF', 'DF', 'GK'],
      '농구': ['센터', '가드', '포워드'],
      '야구': ['투수', '포수', '내야수', '외야수'],
      '배구': ['세터', '리베로', '센터', '레프트', '라이트'],
    };
    for (final entry in options.entries) {
      await tester.tap(find.widgetWithText(FilterChip, entry.key));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<String>).last);
      await tester.pumpAndSettle();
      for (final option in entry.value) {
        expect(find.text(option).hitTestable(), findsWidgets);
      }
      await tester.tap(find.text(entry.value.first).last);
      await tester.pumpAndSettle();
    }
    await tester.tap(find.widgetWithText(FilterChip, '축구'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilterChip, '축구'));
    await tester.pumpAndSettle();
    expect(find.text('FW'), findsNothing);
    await tester.tap(find.byKey(const ValueKey(1)));
    await tester.pumpAndSettle();
    await tester.tap(find.text('GK').last);
    await tester.pumpAndSettle();
    final values = ['member', 'password123', '회원', '서울', '01012345678'];
    for (var i = 0; i < values.length; i++) {
      await tester.enterText(find.byType(TextFormField).at(i), values[i]);
    }
    await tester.tap(find.text('생년월일 선택'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, '회원가입'));
    await tester.pumpAndSettle();
    expect(sent?['c_team'], '무소속');
    expect(sent?['preferred_stocks'], [1, 2, 3, 4]);
    expect(sent?['c_position'], {'1': 'GK', '2': '센터', '3': '투수', '4': '세터'});
    expect(find.text('로그인 화면'), findsOneWidget);
  });

  testWidgets('예약번호로 결제 통합, 취소 탭 필터 및 종목 전환', (tester) async {
    final calls = <Uri>[];
    final api = MemberApi(
      client: MockClient((request) async {
        calls.add(request.url);
        final canceled = request.url.queryParameters['r_category'] == '2';
        final payment = request.url.path.contains('/payment/');
        return http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'results': [
                if (payment)
                  {
                    'r_seq': 7,
                    'p_num': 'P7',
                    'p_amount': 5000,
                    'p_method': '카드',
                  }
                else
                  {
                    'r_seq': 7,
                    'g_name': canceled ? '취소 구장' : '예약 구장',
                    'r_date': '2026-10-26',
                    'rs_time': '08:00',
                    're_time': '10:00',
                    'is_paid': !canceled,
                    'r_c_category': canceled ? '2' : '',
                  },
              ],
            }),
          ),
          200,
        );
      }),
    );
    addTearDown(api.client.close);
    final container = ProviderContainer(
      overrides: [memberApiProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(sessionProvider.notifier).signIn({'c_id': 'member'});
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: HistoryPage())),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('결제번호 P7'), findsOneWidget);
    expect(find.text('결제 이어하기'), findsNothing);
    await tester.tap(find.text('취소'));
    await tester.pumpAndSettle();
    expect(find.text('취소 구장'), findsOneWidget);
    expect(find.text('취소 사유: 우천·기상 악화'), findsOneWidget);
    expect(find.textContaining('결제번호 P7'), findsNothing);
    expect(calls.last.queryParameters['r_category'], '2');
    container.read(sportProvider.notifier).select(3);
    await tester.pumpAndSettle();
    expect(calls.last.path, '/match/reservation/customer/member_03');
  });

  testWidgets('구장 이름과 주소 검색을 분리', (tester) async {
    final api = MemberApi(
      client: MockClient(
        (request) async => http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'results': [
                {
                  'g_name': '서울 구장',
                  'g_address': '부산',
                  'g_num': 10,
                  'g_price': 1000,
                  'g_information': '종목: 축구',
                },
                {
                  'g_name': '부산 구장',
                  'g_address': '서울',
                  'g_num': 10,
                  'g_price': 1000,
                  'g_information': '종목: 축구',
                },
              ],
            }),
          ),
          200,
        ),
      ),
    );
    addTearDown(api.client.close);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [memberApiProvider.overrideWithValue(api)],
        child: const MaterialApp(home: Scaffold(body: GroundsPage())),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '서울');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(find.text('서울 구장'), findsOneWidget);
    expect(find.text('부산 구장'), findsNothing);
    await tester.tap(find.byKey(const ValueKey('groundSearchField')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('장소(주소)').last);
    await tester.pumpAndSettle();
    expect(find.text('부산 구장'), findsOneWidget);
    expect(find.text('서울 구장'), findsNothing);
  });
  // 디버그: 사유 자유 입력·확인 취소·서버 오류 후 재시도·취소 내역 이동 검증.
  // 작업자 : 양태건 / 최종 수정일 : 2026-10-26
  testWidgets('직접 작성한 취소 사유를 저장하고 취소 내역에 표시', (tester) async {
    final reasons = <String>[];
    var canceled = false;
    var reject = true;
    var saved = '';
    final api = MemberApi(
      client: MockClient((request) async {
        if (request.method == 'DELETE') {
          expect(request.url.path, '/cancel/reservation/7');
          expect(request.url.queryParameters['c_id_seq'], 'member_01');
          saved = request.url.queryParameters['r_c_category']!;
          reasons.add(saved);
          if (reject) {
            reject = false;
            return http.Response.bytes(
              utf8.encode(jsonEncode({'detail': '잠시 후 다시 시도해 주세요.'})),
              409,
            );
          }
          canceled = true;
          return http.Response('{}', 200);
        }
        final showCanceled = request.url.queryParameters['r_category'] == '2';
        final rows =
            request.url.path.contains('/payment/') || canceled != showCanceled
            ? []
            : [
                {
                  'r_seq': 7,
                  'g_name': '테스트 구장',
                  'r_date': DateTime.now()
                      .add(const Duration(days: 1))
                      .toIso8601String()
                      .split('T')
                      .first,
                  'rs_time': '08:00',
                  're_time': '10:00',
                  'is_paid': false,
                  'r_check': false,
                  'r_c_category': canceled ? saved : '',
                  'cancel_reason': canceled ? saved : null,
                },
              ];
        return http.Response.bytes(
          utf8.encode(jsonEncode({'results': rows})),
          200,
        );
      }),
    );
    addTearDown(api.client.close);
    final container = ProviderContainer(
      overrides: [memberApiProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(sessionProvider.notifier).signIn({'c_id': 'member'});
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: HistoryPage())),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('예약 취소'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('돌아가기'));
    await tester.pumpAndSettle();
    expect(reasons, isEmpty);
    await tester.tap(find.text('예약 취소'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('취소 확정'));
    await tester.pumpAndSettle();
    expect(find.text('취소 사유를 입력해 주세요.'), findsOneWidget);
    expect(reasons, isEmpty);
    await tester.enterText(find.byType(TextFormField), '   ');
    await tester.tap(find.text('취소 확정'));
    await tester.pumpAndSettle();
    expect(reasons, isEmpty);
    await tester.enterText(
      find.byType(TextFormField),
      '  개인 일정으로 참석이 어렵습니다.  ',
    );
    await tester.tap(find.text('취소 확정'));
    await tester.pumpAndSettle();
    expect(find.textContaining('잠시 후 다시 시도'), findsOneWidget);
    expect(find.text('예약 취소'), findsOneWidget);
    await tester.tap(find.text('예약 취소'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), '개인 일정으로 참석이 어렵습니다.');
    await tester.tap(find.text('취소 확정'));
    await tester.pumpAndSettle();
    expect(reasons, ['개인 일정으로 참석이 어렵습니다.', '개인 일정으로 참석이 어렵습니다.']);
    expect(find.text('취소 사유: 개인 일정으로 참석이 어렵습니다.'), findsOneWidget);
    expect(find.text('예약 취소'), findsNothing);
    expect(find.text('결제 이어하기'), findsNothing);
  });
  // 디버그: 종목·지역 교차 필터와 가입 종목의 예약 ID가 독립적으로 유지되는지 검증.
  // 작업자 : 양태건 / 최종 수정일 : 2026-10-26
  testWidgets('네 종목 전체 탐색, 지역 필터, 미가입 종목 예약 방지', (tester) async {
    tester.view.physicalSize = const Size(390, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = MemberApi(
      client: MockClient(
        (request) async => http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'results': [
                for (final entry in sports.entries)
                  for (final region in ['서울특별시', '경기도'])
                    {
                      'g_code': entry.key,
                      'g_name': '$region ${entry.value}구장',
                      'g_address': '$region 테스트로 1',
                      'g_num': 10,
                      'g_price': 10000,
                      'g_time': '08:00~22:00',
                      'g_information': '시설: 주차 / 종목: ${entry.value} / 성별: 남녀모두',
                    },
              ],
            }),
          ),
          200,
        ),
      ),
    );
    addTearDown(api.client.close);
    final container = ProviderContainer(
      overrides: [memberApiProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'member',
      'c_name': '회원',
      'preferred_stocks': [1],
    });
    await tester.pumpWidget(
      UncontrolledProviderScope(container: container, child: const MyApp()),
    );
    await tester.pumpAndSettle();
    expect(find.byType(GridView), findsOneWidget);
    for (final code in [1, 4, 2, 3]) {
      await tester.ensureVisible(find.byKey(ValueKey('groundSport$code')));
      await tester.tap(find.byKey(ValueKey('groundSport$code')));
      await tester.pumpAndSettle();
      expect(find.text('서울특별시 ${sports[code]}구장'), findsOneWidget);
      expect(find.text('경기도 ${sports[code]}구장'), findsOneWidget);
      expect(container.read(sportProvider), 1);
      expect(tester.takeException(), isNull);
    }
    await tester.tap(find.byKey(const ValueKey('groundRegion')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('서울').last);
    await tester.pumpAndSettle();
    expect(find.text('서울특별시 야구구장'), findsOneWidget);
    expect(find.text('경기도 야구구장'), findsNothing);
    await tester.ensureVisible(find.text('시간 선택 · 예약'));
    await tester.tap(find.text('시간 선택 · 예약'));
    await tester.pumpAndSettle();
    expect(find.text('야구 종목으로 가입한 회원만 예약할 수 있습니다.'), findsOneWidget);
    expect(container.read(memberIdProvider), 'member_01');
    await tester.ensureVisible(find.byKey(const ValueKey('groundRegion')));
    await tester.tap(find.byKey(const ValueKey('groundRegion')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('전체 지역').last);
    await tester.pumpAndSettle();
    expect(find.text('경기도 야구구장'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  // 수정 일 : 2026-10-26 / 작업자 : 양태건
  // 디버그: 기존 답변 표시, 오류 시 입력 보존, 답변의 답변을 부모 ID로 전송합니다.
  testWidgets('문의 답변에 계속 답변하고 실패한 입력을 보존', (tester) async {
    tester.view.physicalSize = const Size(500, 1600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final sent = <Map<String, dynamic>>[];
    final replies = <Map<String, dynamic>>[];
    var reject = true;
    final api = MemberApi(
      client: MockClient((request) async {
        if (request.url.path == '/inquiry/insert') {
          final payload = Map<String, dynamic>.from(
            jsonDecode(request.body) as Map,
          );
          sent.add(payload);
          if (reject) {
            reject = false;
            return http.Response.bytes(
              utf8.encode(jsonEncode({'detail': '다시 시도해 주세요.'})),
              500,
            );
          }
          final level = replies.length + 1;
          replies.add({
            'i_seq': level + 1,
            'i_comment_seq': payload['i_comment_seq'],
            'level': level,
            'post': payload['post'],
            'title': '대화 테스트',
            'i_date': '2026-10-26',
            'inquiry_detail': '후속 안내 $level',
            'h_name': '담당자',
          });
          return http.Response('{}', 201);
        }
        return http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'total': 1,
              'results': [
                {
                  'i_seq': 1,
                  'title': '대화 테스트',
                  'level': 0,
                  'post': '최초 문의 내용',
                  'i_date': '2026-10-26',
                  'inquiry_detail': '기존 관리자 답변',
                  'h_name': '담당자',
                  'replies': replies,
                },
              ],
            }),
          ),
          200,
        );
      }),
    );
    addTearDown(api.client.close);
    final container = ProviderContainer(
      overrides: [memberApiProvider.overrideWithValue(api)],
    );
    addTearDown(container.dispose);
    container.read(sessionProvider.notifier).signIn({'c_id': 'member'});
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: InquiryPage())),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byType(ExpansionTile));
    await tester.pumpAndSettle();
    expect(find.text('기존 관리자 답변'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('replyTo1')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('답변 보내기'));
    await tester.pumpAndSettle();
    expect(find.text('답변 내용을 입력해 주세요.'), findsOneWidget);
    expect(sent, isEmpty);
    await tester.enterText(find.byType(TextFormField), '  추가로 확인 부탁드립니다.  ');
    await tester.tap(find.text('답변 보내기'));
    await tester.pumpAndSettle();
    expect(find.textContaining('다시 시도해 주세요.'), findsOneWidget);
    expect(
      find.widgetWithText(TextFormField, '  추가로 확인 부탁드립니다.  '),
      findsOneWidget,
    );
    await tester.tap(find.text('답변 보내기'));
    await tester.pumpAndSettle();
    expect(find.text('추가로 확인 부탁드립니다.'), findsOneWidget);
    expect(find.text('후속 안내 1'), findsOneWidget);
    await tester.ensureVisible(find.byKey(const ValueKey('replyTo2')));
    await tester.tap(find.byKey(const ValueKey('replyTo2')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextFormField),
      '안내 감사합니다. 한 가지 더 문의합니다.',
    );
    await tester.tap(find.text('답변 보내기'));
    await tester.pumpAndSettle();
    expect(sent[1], {
      'c_id_seq': 'member_01',
      'post': '추가로 확인 부탁드립니다.',
      'i_comment_seq': 1,
    });
    expect(sent[2]['i_comment_seq'], 2);
    expect(find.text('최초 문의 내용'), findsOneWidget);
    expect(find.text('기존 관리자 답변'), findsOneWidget);
    expect(find.text('안내 감사합니다. 한 가지 더 문의합니다.'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
// 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
