// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../inquiry/inquiry_page.dart';
import '../result/result_page.dart';
import '../sanction/sanction_page.dart';
import '../sanction/appeal_page.dart';
import '../announcement/announcement_page.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 확인 가능한 회원 정보와 실제 API로 이동 가능한 메뉴만 제공합니다.
class AccountPage extends ConsumerWidget {
  const AccountPage({
    super.key,
    required this.onReservations,
    required this.onTeams,
  });
  final VoidCallback onReservations;
  final VoidCallback onTeams;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider) ?? {};
    final name = '${session['c_name'] ?? ''}'.trim();
    void open(Widget page) =>
        Navigator.push(context, MaterialPageRoute<void>(builder: (_) => page));
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        MemberPanel(
          color: Colors.white,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 수정 일 : 2026-10-28 / 작업자 : 양태건
              // 목업처럼 프로필을 가로로 배치하고 실제 가입 종목만 표시합니다.
              Row(
                children: [
                  CircleAvatar(
                    radius: 24,
                    backgroundColor: MemberStyle.ink,
                    child: Text(
                      name.isEmpty ? '회' : name.characters.first,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${session['c_name'] ?? '회원'}',
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        Text(
                          '@${session['c_id'] ?? ''}',
                          style: const TextStyle(
                            fontSize: 12,
                            color: MemberStyle.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 6,
                children: [
                  for (final code
                      in (session['preferred_stocks'] as List? ?? []))
                    MemberStatusBadge(
                      sports[int.tryParse('$code')] ?? '$code',
                      color: int.tryParse('$code') == 1
                          ? MemberStyle.green
                          : MemberStyle.blue,
                    ),
                ],
              ),
            ],
          ),
        ),
        const MemberSectionTitle('내 활동'),
        _menu(Icons.calendar_today_outlined, '예약 내역', onReservations),
        _menu(Icons.groups_outlined, '팀 찾기 · 개설', onTeams),
        _menu(
          Icons.sports_score_outlined,
          '경기 결과',
          () => open(const ResultPage()),
        ),
        const MemberSectionTitle('고객지원'),
        _menu(
          Icons.notifications_none,
          '공지사항',
          () => open(const AnnouncementPage()),
        ),
        _menu(
          Icons.support_agent,
          '1:1 문의',
          () => open(
            Scaffold(
              appBar: AppBar(title: const Text('1:1 문의')),
              body: const InquiryPage(),
            ),
          ),
        ),
        _menu(Icons.gavel_outlined, '제재 내역', () => open(const SanctionPage())),
        _menu(
          Icons.fact_check_outlined,
          '이의신청 내역',
          () => open(const AppealPage()),
        ),
        const SizedBox(height: 16),
        TextButton.icon(
          onPressed: () => ref.read(sessionProvider.notifier).signOut(),
          icon: const Icon(Icons.logout),
          label: const Text('로그아웃'),
        ),
      ],
    );
  }

  Widget _menu(IconData icon, String label, VoidCallback onTap) => Container(
    decoration: const BoxDecoration(
      border: Border(bottom: BorderSide(color: MemberStyle.line)),
    ),
    child: ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 0),
      minTileHeight: 54,
      leading: Icon(icon, color: MemberStyle.muted),
      title: Text(
        label,
        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      ),
      trailing: const Icon(
        Icons.chevron_right,
        size: 19,
        color: MemberStyle.muted,
      ),
      onTap: onTap,
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
