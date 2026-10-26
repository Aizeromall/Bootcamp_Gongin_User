// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
// 디버그: 홈은 네 종목 탐색 GridView를 사용하고 다른 탭은 가입 종목 선택을 유지합니다.
// 작업자 : 양태건 / 최종 수정일 : 2026-10-26
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../ground/grounds_page.dart';
import '../history/history_page.dart';
import '../inquiry/inquiry_page.dart';

class MemberHome extends ConsumerStatefulWidget {
  const MemberHome({super.key});
  @override
  ConsumerState<MemberHome> createState() => _MemberHomeState();
}

class _MemberHomeState extends ConsumerState<MemberHome> {
  int tab = 0;
  @override
  Widget build(BuildContext context) {
    final session = ref.watch(sessionProvider)!;
    final available = (session['preferred_stocks'] as List)
        .map((v) => int.tryParse('$v'))
        .whereType<int>()
        .where(sports.containsKey)
        .toSet();
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
        title: const Text.rich(
          TextSpan(
            style: TextStyle(
              fontWeight: FontWeight.w900,
              color: Color(0xFF141A24),
              fontSize: 25,
            ),
            children: [
              TextSpan(text: '공 '),
              TextSpan(
                text: 'In',
                style: TextStyle(
                  color: Color(0xFF1976F9),
                  fontStyle: FontStyle.italic,
                ),
              ),
              TextSpan(text: ' 중개사'),
            ],
          ),
        ),
        actions: [
          if (tab != 0)
            DropdownButton<int>(
              value: ref.watch(sportProvider),
              underline: const SizedBox(),
              items: available
                  .map(
                    (s) => DropdownMenuItem(value: s, child: Text(sports[s]!)),
                  )
                  .toList(),
              onChanged: (v) {
                if (v != null) {
                  ref.read(sportProvider.notifier).select(v);
                }
              },
            ),
          IconButton(
            tooltip: '로그아웃',
            onPressed: () => ref.read(sessionProvider.notifier).signOut(),
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: [
        const GroundsPage(),
        const HistoryPage(),
        const InquiryPage(),
      ][tab],
      bottomNavigationBar: NavigationBar(
        backgroundColor: Colors.white,
        indicatorColor: const Color(0xFFE8F0FF),
        selectedIndex: tab,
        onDestinationSelected: (v) => setState(() => tab = v),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: '홈'),
          NavigationDestination(
            icon: Icon(Icons.receipt_long_outlined),
            label: '내 예약·결제',
          ),
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            label: '문의',
          ),
        ],
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
