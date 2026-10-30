// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'vm/auth_refresh_state.dart';
import 'vm/member_state.dart';
import 'vm/notification_state.dart';
import 'vm/social_login_state.dart';
import 'vm/theme_state.dart';
import 'view/history/reservation_detail_page.dart';
import 'view/chat/chat_page.dart';
import 'view/shared/member_style.dart';
import 'view/auth/login_page.dart';
import 'view/auth/welcome_page.dart';
import 'view/home/member_home.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 로그아웃 시 열려 있는 보호 화면도 닫아 이전 회원 정보 노출을 막습니다.
// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 전체 회원 목업의 화면 흐름과 공통 스타일을 적용합니다.

class MyApp extends ConsumerStatefulWidget {
  const MyApp({super.key});
  @override
  ConsumerState<MyApp> createState() => _MyAppState();
}

class _MyAppState extends ConsumerState<MyApp> {
  final navigator = GlobalKey<NavigatorState>();
  late bool started;

  // 수신 payload는 NotificationState에서 현재 계정 소유 여부를 확인합니다.
  void openNotification(Map<String, dynamic> data) {
    final session = ref.read(sessionProvider);
    if (session == null) return;
    final members = session['member_ids'] as List? ?? [session['c_id_seq']];
    if (!members.contains(data['c_id_seq'])) return;
    final member = data['c_id_seq'] as String?;
    final sport = int.tryParse(member?.split('_').last ?? '');
    if (sport != null && sports.containsKey(sport)) {
      ref.read(sportProvider.notifier).select(sport);
    }
    final seq = int.tryParse('${data['r_seq']}');
    navigator.currentState?.push(
      MaterialPageRoute<void>(
        builder: (_) => data['type'] == 'message'
            ? Scaffold(
                appBar: AppBar(title: const Text('메시지')),
                body: const ChatPage(),
              )
            : seq != null
            ? ReservationDetailPage(seq: seq)
            : const MemberHome(),
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    started = ref.read(sessionProvider) != null;
    // 수정 일 : 2026-10-30 / 작업자 : 김병재
    // 앱 재실행 시 보안 저장소의 로그인 토큰으로 자동 로그인을 시도합니다.
    if (!started) restoreSession();
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 자동 로그인: 성공하면 일반 로그인과 같은 acceptMemberSession으로 세션·종목을 설정합니다.
  // 실패(저장 토큰 없음·30일 경과·서버 연결 실패)하면 기존 시작·로그인 화면을 그대로 사용합니다.
  Future<void> restoreSession() async {
    final result = await ref.read(authRefreshProvider).restore();
    // 확인 중 사용자가 직접 로그인했다면 그 세션을 덮어쓰지 않습니다.
    if (!mounted || result == null || ref.read(sessionProvider) != null) {
      return;
    }
    try {
      acceptMemberSession(ref, result);
    } catch (_) {
      // 가입 종목 정보가 없는 응답은 자동 로그인하지 않고 시작 화면을 유지합니다.
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(notificationProvider);
    ref.watch(socialLogoutProvider);
    ref.listen(notificationProvider, (previous, next) {
      final data = next['message'];
      if (data is! Map<String, dynamic> ||
          identical(previous?['message'], data)) {
        return;
      }
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || ref.read(sessionProvider) == null) return;
        if (next['open'] == true) {
          openNotification(data);
        } else {
          final context = navigator.currentContext;
          if (context != null) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(notificationTitles[data['type']] ?? '새 알림'),
                action: SnackBarAction(
                  label: '확인',
                  onPressed: () => openNotification(data),
                ),
              ),
            );
          }
        }
        ref.read(notificationProvider.notifier).clearMessage();
      });
    });
    ref.listen(sessionProvider, (previous, next) {
      // 수정 일 : 2026-10-30 / 작업자 : 김병재
      // 모든 로그인 경로(일반·간편·가입·복구·회원정보 수정)의 새 토큰을 보안 저장소에 저장하고,
      // 로그아웃·계정 삭제 신청으로 세션이 비워지면 저장된 토큰도 지워 자동 로그인을 막습니다.
      final storage = ref.read(sessionStorageProvider);
      final token = next?['access_token'];
      if (next == null) {
        storage.clear();
      } else if (token is String && token.isNotEmpty) {
        storage.save(token);
      }
      if (next == null && previous != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) {
            navigator.currentState?.popUntil((route) => route.isFirst);
          }
        });
      }
    });
    return MaterialApp(
      navigatorKey: navigator,
      title: '공IN 중개사',
      debugShowCheckedModeBanner: false,
      themeMode: ref.watch(themeModeProvider),
      darkTheme: ThemeData(
        useMaterial3: true,
        fontFamily: 'IBM Plex Sans KR',
        fontFamilyFallback: const ['Apple Color Emoji', 'Noto Color Emoji'],
        // 수정 일 : 2026-10-30 / 작업자 : 최현준
        // 라이트·다크 화면에서 동일한 본문 크기와 줄 간격을 사용합니다.
        textTheme: const TextTheme(
          bodyLarge: TextStyle(fontSize: 15, height: 1.55),
          bodyMedium: TextStyle(fontSize: 14, height: 1.5),
          titleLarge: TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
          titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
        ),
        colorScheme: ColorScheme.fromSeed(
          seedColor: MemberStyle.blue,
          brightness: Brightness.dark,
          surface: const Color(0xFF141922),
        ),
        scaffoldBackgroundColor: const Color(0xFF10151D),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF10151D),
          foregroundColor: Color(0xFFE7ECF5),
          surfaceTintColor: Colors.transparent,
        ),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
          filled: true,
          fillColor: Color(0xFF242C38),
        ),
      ),
      theme: ThemeData(
        fontFamily: 'IBM Plex Sans KR',
        fontFamilyFallback: const ['Apple Color Emoji', 'Noto Color Emoji'],
        useMaterial3: true,
        // 수정 일 : 2026-10-27 / 작업자 : 양태건
        // 흰 바탕·파란 주요 동작과 초록 종목 선택을 홈 목업 기준으로 적용합니다.
        colorScheme: ColorScheme.fromSeed(seedColor: MemberStyle.blue).copyWith(
          primary: MemberStyle.blue,
          onPrimary: Colors.white,
          secondaryContainer: const Color(0xFFEAF2FF),
          onSecondaryContainer: MemberStyle.blue,
          surface: Colors.white,
          onSurface: MemberStyle.ink,
        ),
        scaffoldBackgroundColor: Colors.white,
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.white,
          foregroundColor: MemberStyle.ink,
          surfaceTintColor: Colors.transparent,
          elevation: 0,
          centerTitle: false,
          titleTextStyle: TextStyle(
            fontFamily: 'IBM Plex Sans KR',
            fontSize: 18,
            fontWeight: FontWeight.w800,
            color: MemberStyle.ink,
          ),
        ),
        // 수정 일 : 2026-10-28 / 작업자 : 양태건
        // 목업의 작은 제목·본문·윤곽선 카드를 공통 적용합니다.
        textTheme: const TextTheme(
          bodyLarge: TextStyle(fontSize: 15, height: 1.55),
          bodyMedium: TextStyle(fontSize: 14, height: 1.5),
          titleLarge: TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
          titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            foregroundColor: MemberStyle.ink,
            side: const BorderSide(color: MemberStyle.line),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
          ),
        ),
        dividerTheme: const DividerThemeData(
          color: MemberStyle.line,
          thickness: 1,
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            elevation: 0,
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
            textStyle: const TextStyle(
              fontWeight: FontWeight.w700,
              fontFamily: 'IBM Plex Sans KR',
            ),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: Colors.white,
          surfaceTintColor: Colors.transparent,
          indicatorColor: Colors.transparent,
          height: 76,
          labelTextStyle: WidgetStateProperty.resolveWith(
            (states) => TextStyle(
              fontSize: 12,
              fontFamily: 'IBM Plex Sans KR',
              height: 1.25,
              fontWeight: states.contains(WidgetState.selected)
                  ? FontWeight.w800
                  : FontWeight.w500,
              color: states.contains(WidgetState.selected)
                  ? const Color(0xFF172541)
                  : const Color(0xFF999FAE),
            ),
          ),
          iconTheme: WidgetStateProperty.resolveWith(
            (states) => IconThemeData(
              size: 27,
              color: states.contains(WidgetState.selected)
                  ? const Color(0xFF172541)
                  : const Color(0xFF999FAE),
            ),
          ),
        ),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            borderSide: BorderSide(color: MemberStyle.line),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            borderSide: BorderSide(color: MemberStyle.line),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
            borderSide: BorderSide(color: MemberStyle.blue),
          ),
          filled: true,
          fillColor: MemberStyle.surface,
        ),
        cardTheme: CardThemeData(
          elevation: 0,
          color: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: const BorderSide(color: MemberStyle.line),
          ),
        ),
      ),
      // 수정 일 : 2026-10-30 / 작업자 : 김병재
      // 자동 로그인 확인 중에도 기존 시작 화면을 그대로 보여주고, 성공하면 세션 변경으로 홈으로 이동합니다.
      home: ref.watch(sessionProvider) == null
          ? started
                ? const LoginPage()
                : WelcomePage(onStart: () => setState(() => started = true))
          : const MemberHome(),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (FCM 수신 및 기존 화면 연결)
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (앱 재실행 시 자동 로그인·로그인 토큰 보안 저장)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (화면 모드 및 다크 테마 연결)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
