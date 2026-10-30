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
import 'package:bootcamp_project_gongin_admin_app/view/reservation/reservation_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/payment/payment_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/team_match/team_match_post_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/sanction/sanction_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/result/result_page.dart';
import 'package:bootcamp_project_gongin_admin_app/view/auth/register_page.dart';

http.Response response(Object body, [int status = 200]) =>
    http.Response.bytes(utf8.encode(jsonEncode(body)), status);
ProviderContainer setup(
  Future<http.Response> Function(http.Request) handler, {
  bool login = true,
}) {
  final api = MemberApi(client: MockClient(handler));
  final container = ProviderContainer(
    overrides: [memberApiProvider.overrideWithValue(api)],
  );
  if (login) {
    container.read(sessionProvider.notifier).signIn({
      'c_id': 'member',
      'c_name': '김민준',
      'preferred_stocks': [1],
      'access_token': 'mock-token',
    });
  }
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
Future<void> snapshot(WidgetTester tester, String name) async {
  const path = String.fromEnvironment('MEMBER_PREVIEW_PATH');
  if (path.isEmpty) return;
  await tester.runAsync(() async {
    final boundary = tester.renderObject<RenderRepaintBoundary>(
      find.byKey(const ValueKey('memberPreview')),
    );
    final image = await boundary.toImage(pixelRatio: 2);
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    await File('$path-$name.png').writeAsBytes(bytes!.buffer.asUint8List());
    image.dispose();
  });
}

void main() {
  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  testWidgets('시작·로그인·MY 흐름과 실제 API 메뉴', (tester) async {
    final font = FontLoader('IBM Plex Sans KR')
      ..addFont(rootBundle.load('assets/fonts/IBMPlexSansKR-Regular.ttf'));
    await font.load();
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final container = setup((r) async {
      if (r.url.path == '/auth/login') {
        return response({
          'c_id': 'member',
          'c_name': '김민준',
          'preferred_stocks': [1],
        });
      }
      return response({'results': []});
    }, login: false);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const RepaintBoundary(
          key: ValueKey('memberPreview'),
          child: MyApp(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await snapshot(tester, 'welcome');
    await tester.tap(find.text('시작하기'));
    await tester.pumpAndSettle();
    await snapshot(tester, 'login');
    await tester.enterText(find.byType(TextFormField).at(0), 'member');
    await tester.enterText(find.byType(TextFormField).at(1), 'password123');
    await tester.tap(find.text('로그인'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('MY'));
    await tester.pumpAndSettle();
    await snapshot(tester, 'my');
    expect(find.text('경기 결과'), findsOneWidget);
    expect(find.text('회원정보 수정'), findsNothing);
    await tester.ensureVisible(find.text('경기 결과'));
    await tester.tap(find.text('경기 결과'));
    await tester.pumpAndSettle();
    expect(find.byType(ResultPage), findsOneWidget);
    expect(tester.takeException(), isNull);
    const previewPath = String.fromEnvironment('MEMBER_PREVIEW_PATH');
    if (previewPath.isNotEmpty) {
      await tester.pageBack();
      await tester.pumpAndSettle();
      final navigator = tester.state<NavigatorState>(find.byType(Navigator));
      navigator.push(
        MaterialPageRoute<void>(builder: (_) => const RegisterPage()),
      );
      await tester.pumpAndSettle();
      await snapshot(tester, 'register-account');
      for (final entry in {
        'c_id': 'new_member',
        'c_pw': 'password123',
        'confirmPassword': 'password123',
        'c_phone': '01012345678',
      }.entries) {
        await tester.enterText(find.byKey(ValueKey(entry.key)), entry.value);
      }
      await tester.tap(find.text('다음'));
      await tester.pumpAndSettle();
      await snapshot(tester, 'register-profile');
      navigator.pop();
      await tester.pumpAndSettle();
      navigator.push(
        MaterialPageRoute<void>(
          builder: (_) => const PaymentPage(
            rSeq: 1,
            memberId: 'member_01',
            groundName: '마포 하늘풋살파크 A구장',
            expectedAmount: 10000,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await snapshot(tester, 'payment');
      navigator.pop();
      await tester.pumpAndSettle();
    }
  });
  testWidgets('전체 대여는 별도 슬롯·생성 API를 사용하고 금액을 전체 요금으로 전달', (tester) async {
    Map<String, dynamic>? body;
    final paths = <String>[];
    final container = setup((r) async {
      paths.add(r.url.path);
      if (r.method == 'POST') {
        body = Map<String, dynamic>.from(jsonDecode(r.body));
        return response({'r_seq': 19}, 201);
      }
      return response({
        'slots': [
          {'rs_time': '08:00', 're_time': '10:00', 'is_available': true},
        ],
      });
    });
    await tester.pumpWidget(
      app(
        container,
        const ReservationPage(
          ground: {
            'g_code': 3,
            'g_name': '구장',
            'g_address': '서울',
            'g_price': 100000,
            'g_num': 10,
          },
          rental: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('날짜 선택'));
    await tester.pumpAndSettle();
    final tomorrow = DateUtils.dateOnly(
      DateTime.now().add(const Duration(days: 1)),
    );
    tester
        .widget<CalendarDatePicker>(find.byType(CalendarDatePicker))
        .onDateChanged(tomorrow);
    await tester.pump();
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('08:00'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('예약하고 결제 선택'));
    await tester.pumpAndSettle();
    expect(
      paths,
      containsAll(['/ground/reservation/slots/3', '/ground/reservation']),
    );
    expect(body?['c_id_seq'], 'member_01');
    expect(body?['rs_time'], '08:00');
    expect(find.byType(PaymentPage), findsOneWidget);
    expect(
      tester.widget<PaymentPage>(find.byType(PaymentPage)).expectedAmount,
      100000,
    );
  });
  testWidgets('매칭 글은 선택한 대여 예약 번호를 전송', (tester) async {
    Map<String, dynamic>? saved;
    final container = setup((r) async {
      if (r.url.path == '/team_match/lineup-options') {
        return response({
          'required_count': 1,
          'results': [
            {'c_id_seq': 'member_01', 'c_name': '회원'},
          ],
        });
      }
      if (r.method == 'POST') {
        saved = Map<String, dynamic>.from(jsonDecode(r.body));
        return response({'bulletin_seq': 4}, 201);
      }
      return response({
        'results': [
          {
            'r_seq': 7,
            'g_name': '대여 구장',
            'r_date': '2026-11-01',
            'rs_time': '16:00',
            're_time': '18:00',
            'has_post': false,
          },
        ],
      });
    });
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          initialRoute: '/create',
          routes: {
            '/': (_) => const Scaffold(body: Text('목록')),
            '/create': (_) => const TeamMatchPostPage(),
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('대여 구장'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '상대 팀 구해요');
    await tester.tap(find.text('매칭 글 등록'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    await tester.tap(find.text('선택 완료'));
    await tester.pumpAndSettle();
    expect(saved, {
      'c_id_seq': 'member_01',
      'r_seq': 7,
      'board_content': '상대 팀 구해요',
      'member_ids': ['member_01'],
    });
    expect(find.text('목록'), findsOneWidget);
  });
  testWidgets('제재에서 이의신청 전송과 실패 입력 보존', (tester) async {
    var attempts = 0;
    Map<String, dynamic>? body;
    final container = setup((r) async {
      if (r.method == 'POST') {
        body = Map<String, dynamic>.from(jsonDecode(r.body));
        return ++attempts == 1
            ? response({'detail': '다시 시도해 주세요.'}, 500)
            : response({'result': 'OK'}, 201);
      }
      return response({
        'warning_count': 1,
        'notice': '제재 안내',
        'results': [
          {
            'cs_seq': 5,
            'sanction_type': '경고',
            'tag': '경고',
            'cs_detail': '지각',
            'cs_date': '2026-10-28',
            'appeal_deadline': '2026-11-04',
            'can_appeal': true,
          },
        ],
      });
    });
    await tester.pumpWidget(app(container, const SanctionPage()));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('이의신청 하기'));
    await tester.tap(find.text('이의신청 하기'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).first, '시간에 맞춰 도착했습니다.');
    await tester.tap(find.text('이의신청 제출'));
    await tester.pumpAndSettle();
    expect(find.text('시간에 맞춰 도착했습니다.'), findsOneWidget);
    await tester.tap(find.text('이의신청 제출'));
    await tester.pumpAndSettle();
    expect(body?['cs_seq'], 5);
    expect(body?['a_type'], '사실과 다름');
    expect(body?['c_id_seq'], 'member_01');
    expect(body?['a_evidence'], isEmpty);
    expect(attempts, 2);
    expect(tester.takeException(), isNull);
  });
  testWidgets('다른 회원 결과 상세는 표시하지 않음', (tester) async {
    final container = setup(
      (r) async => response({
        'c_id_seq': 'other_01',
        'g_name': '다른 회원의 경기',
        'c_r_r_score': 10,
      }),
    );
    await tester.pumpWidget(app(container, const ResultPage(seq: 7)));
    await tester.pumpAndSettle();
    expect(find.text('현재 회원의 경기 기록이 아닙니다.'), findsOneWidget);
    expect(find.text('다른 회원의 경기'), findsNothing);
  });
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
