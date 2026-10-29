// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/notification_state.dart';
import '../ground/grounds_page.dart';
import '../history/history_page.dart';
import '../inquiry/inquiry_page.dart';
import '../team/team_page.dart';
import '../board/board_page.dart';
import '../chat/chat_page.dart';
import '../announcement/announcement_page.dart';
import '../shared/member_style.dart';
import '../account/account_page.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 첨부 목업의 홈·예약·팀·메시지·MY 구조를 사용하고 게시판은 홈 바로가기로 연결합니다.
class MemberHome extends ConsumerStatefulWidget {
  const MemberHome({super.key});
  @override
  ConsumerState<MemberHome> createState() => _MemberHomeState();
}

class _MemberHomeState extends ConsumerState<MemberHome> {
  int tab = 0;
  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  // 게시판 자체 AppBar를 사용하여 중복 헤더 없이 이동합니다.
  void openBoard({bool matching = false}) {
    Navigator.push(
      context,
      MaterialPageRoute<void>(
        builder: (_) => BoardPage(initialCategory: matching ? '매칭신청' : '전체'),
      ),
    );
  }

  void openInquiry() => Navigator.push(
    context,
    MaterialPageRoute<void>(
      builder: (_) => Scaffold(
        appBar: AppBar(title: const Text('문의')),
        body: const InquiryPage(),
      ),
    ),
  );
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
        toolbarHeight: tab == 0 ? 76 : 64,
        titleSpacing: 16,
        title: tab == 0
            ? const FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SizedBox(
                      width: 29,
                      height: 34,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          Icon(
                            Icons.sports_soccer,
                            size: 25,
                            color: MemberStyle.green,
                          ),
                          Positioned(
                            right: 0,
                            top: 0,
                            child: Icon(
                              Icons.directions_run,
                              size: 13,
                              color: MemberStyle.blue,
                            ),
                          ),
                        ],
                      ),
                    ),
                    SizedBox(width: 8),
                    Text.rich(
                      TextSpan(
                        style: TextStyle(
                          fontSize: 27,
                          fontWeight: FontWeight.w900,
                          color: MemberStyle.ink,
                          letterSpacing: -1,
                        ),
                        children: [
                          TextSpan(text: '공 '),
                          TextSpan(
                            text: 'In',
                            style: TextStyle(
                              color: MemberStyle.blue,
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                          TextSpan(text: ' 중개사'),
                        ],
                      ),
                    ),
                  ],
                ),
              )
            : Text(
                ['홈', '내 예약·결제', '팀', '메시지', 'MY'][tab],
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
        actions: [
          IconButton(
            tooltip: '푸시 알림 설정',
            icon: const Icon(Icons.notifications_active_outlined),
            onPressed: () => showModalBottomSheet<void>(
              context: context,
              builder: (context) => Consumer(
                builder: (context, ref, _) => SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text(
                          '푸시 알림',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text('${ref.watch(notificationProvider)['status']}'),
                        const Text(
                          '채팅 메시지 · 매치 성사 · 경기 시작 10분 전 · 시작 10분 후 미출석 안내',
                        ),
                        const SizedBox(height: 12),
                        const Text('알림이 차단된 경우 Android 설정에서 앱 알림을 허용해 주세요.'),
                        TextButton(
                          onPressed: () =>
                              ref.read(notificationProvider.notifier).retry(),
                          child: const Text('권한 확인 및 다시 연결'),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          if (tab != 0)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: DropdownButton<int>(
                value: ref.watch(sportProvider),
                underline: const SizedBox(),
                items: available
                    .map(
                      (s) =>
                          DropdownMenuItem(value: s, child: Text(sports[s]!)),
                    )
                    .toList(),
                onChanged: (value) {
                  if (value != null) {
                    ref.read(sportProvider.notifier).select(value);
                  }
                },
              ),
            ),
          IconButton(
            tooltip: '공지사항',
            icon: const Icon(Icons.notifications_none_rounded, size: 29),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute<void>(builder: (_) => const AnnouncementPage()),
            ),
          ),
          PopupMenuButton<String>(
            tooltip: '회원 메뉴',
            icon: const Icon(Icons.more_horiz),
            onSelected: (value) {
              if (value == 'inquiry') openInquiry();
              if (value == 'logout') {
                ref.read(sessionProvider.notifier).signOut();
              }
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'inquiry', child: Text('문의')),
              PopupMenuItem(value: 'logout', child: Text('로그아웃')),
            ],
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: KeyedSubtree(
        key: ValueKey('$tab-${ref.watch(memberIdProvider)}'),
        child: [
          GroundsPage(
            onOpenBoard: () => openBoard(),
            onOpenTeamMatch: () => openBoard(matching: true),
          ),
          const HistoryPage(),
          const TeamPage(),
          const ChatPage(),
          AccountPage(
            onReservations: () => setState(() => tab = 1),
            onTeams: () => setState(() => tab = 2),
          ),
        ][tab],
      ),
      bottomNavigationBar: DecoratedBox(
        decoration: const BoxDecoration(
          border: Border(top: BorderSide(color: MemberStyle.line)),
        ),
        child: NavigationBar(
          selectedIndex: tab,
          onDestinationSelected: (value) => setState(() => tab = value),
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home_rounded),
              label: '홈',
            ),
            NavigationDestination(
              icon: Icon(Icons.calendar_today_outlined),
              label: '예약',
            ),
            NavigationDestination(
              icon: Icon(Icons.groups_outlined),
              label: '팀',
            ),
            NavigationDestination(
              icon: Icon(Icons.send_outlined),
              label: '메시지',
            ),
            NavigationDestination(
              icon: Icon(Icons.person_outline),
              label: 'MY',
            ),
          ],
        ),
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (푸시 연결 상태 및 재시도)
