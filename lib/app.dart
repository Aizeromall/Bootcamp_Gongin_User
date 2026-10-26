// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'vm/member_state.dart';
import 'view/auth/login_page.dart';
import 'view/home/member_home.dart';

class MyApp extends ConsumerWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) => MaterialApp(
    title: '공IN 중개사',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      fontFamily: 'IBM Plex Sans KR',
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF298653)),
      scaffoldBackgroundColor: const Color(0xFFF5F8F2),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
        filled: true,
        fillColor: Colors.white,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
    ),
    home: ref.watch(sessionProvider) == null
        ? const LoginPage()
        : const MemberHome(),
  );
}
// 최종 수정 일 : 2026-10-24
