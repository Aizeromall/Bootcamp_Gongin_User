// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
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
      appBar: AppBar(
        title: const Text(
          '공IN 중개사',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
        actions: [
          DropdownButton<int>(
            value: ref.watch(sportProvider),
            underline: const SizedBox(),
            items: available
                .map((s) => DropdownMenuItem(value: s, child: Text(sports[s]!)))
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
        selectedIndex: tab,
        onDestinationSelected: (v) => setState(() => tab = v),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.stadium_outlined),
            label: '구장 찾기',
          ),
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
// 최종 수정 일 : 2026-10-24
