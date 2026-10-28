// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'vm/member_state.dart';
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
  @override
  void initState() {
    super.initState();
    started = ref.read(sessionProvider) != null;
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(sessionProvider, (previous, next) {
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
      theme: ThemeData(
        fontFamily: 'IBM Plex Sans KR',
        fontFamilyFallback: const ['Apple Color Emoji', 'Noto Color Emoji'],
        useMaterial3: true,
        // 수정 일 : 2026-10-27 / 작업자 : 양태건
        // 흰 바탕·파란 주요 동작과 초록 종목 선택을 홈 목업 기준으로 적용합니다.
        colorScheme: ColorScheme.fromSeed(seedColor: MemberStyle.blue).copyWith(
          primary: MemberStyle.blue,
          onPrimary: Colors.white,
          surface: Colors.white,
          onSurface: MemberStyle.ink,
        ),
        scaffoldBackgroundColor: Colors.white,
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.white,
          foregroundColor: MemberStyle.ink,
          surfaceTintColor: Colors.transparent,
          elevation: 0,
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
            borderRadius: BorderRadius.circular(20),
          ),
        ),
      ),
      home: ref.watch(sessionProvider) == null
          ? started
                ? const LoginPage()
                : WelcomePage(onStart: () => setState(() => started = true))
          : const MemberHome(),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
