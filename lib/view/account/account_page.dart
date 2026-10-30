// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import 'account_profile_page.dart';
import 'settings_page.dart';
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
        // 수정 일 : 2026-10-29 / 작업자 : 최현준 — MY 프로필 카드를 회원정보 수정에 연결합니다.
        Semantics(
          button: true,
          label: '회원정보 수정',
          child: InkWell(
            onTap: () => open(const AccountProfilePage()),
            borderRadius: BorderRadius.circular(18),
            child: MemberPanel(
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
                      const Icon(
                        Icons.edit_outlined,
                        color: MemberStyle.muted,
                        size: 20,
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
          ),
        ),
        // 수정 일 : 2026-10-30 / 작업자 : 최현준
        // 가입 종목별 서버 통계를 좌우로 넘겨 확인합니다.
        const MemberSectionTitle('종목별 티어'),
        SizedBox(
          height: 270,
          child: PageView(
            children: [
              for (final id in ref.watch(memberIdsProvider))
                _TierCard(memberId: id),
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
        _menu(Icons.settings_outlined, '설정', () => open(const SettingsPage())),
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

class _TierCard extends ConsumerWidget {
  const _TierCard({required this.memberId});
  final String memberId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = apiQuery('/rating/summary/${Uri.encodeComponent(memberId)}');
    return MemberPanel(
      child: ref
          .watch(apiDocumentProvider(query))
          .when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (_, _) => Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text('티어 정보를 불러오지 못했습니다.'),
                TextButton(
                  onPressed: () => ref.invalidate(apiDocumentProvider(query)),
                  child: const Text('다시 시도'),
                ),
              ],
            ),
            data: (data) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${sports[sportOfMember(memberId)] ?? '종목'}  ·  좌우로 넘겨보기'),
                const SizedBox(height: 8),
                Text(
                  '${data['tier'] ?? '티어 미확인'}',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                Text('경기 ${data['total_matches'] ?? '미확인'}회'),
                const SizedBox(height: 8),
                Expanded(child: _SportTotals(memberId: memberId)),
              ],
            ),
          ),
    );
  }
}

// 수정 일 : 2026-10-30 / 작업자 : 최현준
// 회원별 경기 결과의 확인된 종목 스탯만 합산합니다.
class _SportTotals extends ConsumerWidget {
  const _SportTotals({required this.memberId});
  final String memberId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = apiQuery(
      '/match/result/customer/${Uri.encodeComponent(memberId)}',
    );
    return ref
        .watch(apiDocumentProvider(query))
        .when(
          loading: () => const Text('스탯 조회 중…'),
          error: (_, _) => TextButton(
            onPressed: () => ref.invalidate(apiDocumentProvider(query)),
            child: const Text('스탯 조회 실패 · 다시 시도'),
          ),
          data: (data) {
            final rows = apiRows(data);
            if (rows.isEmpty) return const Text('경기 스탯 기록이 없습니다.');
            final totals = <String, int>{};
            var incomplete = false;
            for (final row in rows) {
              if (row['c_id_seq'] != memberId) {
                incomplete = true;
                continue;
              }
              final sport = sportOfMember(memberId);
              final expected = {
                1: {'SOCCER', '1', '01'},
                2: {'BASKETBALL', '2', '02'},
                3: {'BASEBALL', '3', '03'},
                4: {'VOLLEYBALL', '4', '04'},
              }[sport];
              if (expected == null ||
                  !expected.contains('${row['e_code']}'.toUpperCase())) {
                incomplete = true;
                continue;
              }
              final stats = resultStats(
                row['c_r_r_statcode'],
                sport: row['e_code'],
              );
              if (stats == null) {
                incomplete = true;
                continue;
              }
              for (final entry in stats.entries) {
                totals.update(
                  entry.key,
                  (value) => value + int.parse(entry.value),
                  ifAbsent: () => int.parse(entry.value),
                );
              }
            }
            if (totals.isEmpty) return const Text('스탯 기록을 확인할 수 없습니다.');
            return SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: 12,
                    runSpacing: 6,
                    children: [
                      for (final entry in totals.entries)
                        Text('${entry.key} ${entry.value}'),
                    ],
                  ),
                  if (incomplete) const Text('일부 기록은 형식을 확인할 수 없어 합산하지 않았습니다.'),
                ],
              ),
            );
          },
        );
  }
}
// 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (설정 진입)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
