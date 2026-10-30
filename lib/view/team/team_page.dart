// 2026-10-27
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/auth_refresh_state.dart';
import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../../vm/my_team_state.dart';
import '../../vm/team_state.dart';
import '../board/board_page.dart';
import '../chat/chat_room_page.dart';
import '../shared/api_content.dart';
import '../shared/ui.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../team_match/team_match_post_page.dart';
import 'team_create_page.dart';
import 'team_detail_page.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 팀 생성·가입 신청·탈퇴·폐지를 실제 API와 연결합니다. 권한 판단은 서버가 최종 수행합니다.
// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 팀 탭 목업 적용: 종목 Dropdown 대신 가입한 모든 종목의 소속팀을 카드로 보여줍니다.
//   - 팀이 있는 종목: 팀 배너(등급) + 팀장은 팀원 모집·경기 매칭·팀 채팅·가입 신청 관리, 모두 팀원 목록
//   - 팀이 없는 종목: 그 종목 팀 목록(개설자 ID 끝자리로 종목 판단)에서 가입 신청하거나 직접 개설
//   - 개설·가입은 선호(가입) 종목에서 팀이 없는 종목만 가능하며, 그 종목의 내 회원 ID로 요청합니다.
class TeamPage extends ConsumerStatefulWidget {
  const TeamPage({super.key});
  @override
  ConsumerState<TeamPage> createState() => _TeamPageState();
}

class _TeamPageState extends ConsumerState<TeamPage> {
  final search = TextEditingController();
  String keyword = '';
  // 선택한 종목 카드입니다. 없으면 현재 선택 종목(없으면 첫 종목)을 보여줍니다.
  int? selected;
  bool busy = false;

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 서버 최대 100개를 받아 앱에서 종목으로 거릅니다(페이지마다 개수가 달라지는 문제 방지).
  ApiQuery get listQuery =>
      apiQuery('/team/select', {'keyword': keyword, 'limit': '100'});

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 가입 신청·탈퇴·폐지 공통 처리: 확인 대화상자 → 서버 성공 후에만 안내·관련 조회 갱신.
  Future<void> run(
    Future<void> Function() action, {
    String? confirm,
    required String done,
  }) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      if (confirm != null) {
        final ok = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(confirm),
            content: const Text('진행하시겠어요?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('돌아가기'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('확인'),
              ),
            ],
          ),
        );
        if (ok != true || !mounted) return;
      }
      await action();
      if (!mounted) return;
      ref.invalidate(teamDataRefreshProvider);
      ref.invalidate(apiDocumentProvider);
      showMessage(context, done);
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 게시판·팀 매칭 등 기존 화면은 현재 선택 종목의 회원 ID를 사용하므로, 팀 종목으로 맞춘 뒤 이동합니다.
  void openAs(int sport, Widget page) {
    final navigator = Navigator.of(context);
    ref.read(sportProvider.notifier).select(sport);
    navigator.push(MaterialPageRoute<void>(builder: (_) => page));
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 팀 채팅: 팀 종목 회원 ID로 채팅 인증 후 채팅방을 만들고(기본 이름 = 소속팀명) 바로 입장합니다.
  Future<void> openTeamChat(SportTeam entry) async {
    if (busy) return;
    final navigator = Navigator.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() => busy = true);
    try {
      ref.read(sportProvider.notifier).select(entry.sport);
      final token = await ref.read(authRefreshProvider).issueChat();
      if (token == null) throw Exception('채팅 연결을 확인하지 못했습니다. 다시 시도해 주세요.');
      final room = await ref
          .read(memberApiProvider)
          .request('/chat/rooms', body: const {}, accessToken: token);
      await navigator.push(
        MaterialPageRoute<void>(builder: (_) => ChatRoomPage(room: room)),
      );
    } catch (error) {
      messenger.showSnackBar(
        SnackBar(content: Text('$error'.replaceFirst('Exception: ', ''))),
      );
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ref
        .watch(myTeamProvider)
        .when(
          skipLoadingOnRefresh: false,
          loading: () => pageContent([
            const Padding(
              padding: EdgeInsets.all(32),
              child: Center(child: CircularProgressIndicator()),
            ),
          ]),
          error: (error, _) => pageContent([
            Text('$error'.replaceFirst('Exception: ', '')),
            TextButton(
              onPressed: () => ref.invalidate(myTeamProvider),
              child: const Text('소속팀 다시 조회'),
            ),
          ]),
          data: (entries) {
            if (entries.isEmpty) {
              return pageContent([const Text('가입한 종목이 없습니다.')]);
            }
            final want = selected ?? ref.watch(sportProvider);
            final current = entries.firstWhere(
              (e) => e.sport == want,
              orElse: () => entries.first,
            );
            return pageContent([
              Row(
                children: const [
                  Text(
                    '종목별 소속 팀',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                  ),
                  Spacer(),
                  Text(
                    '종목당 1개 팀만 가입 가능',
                    style: TextStyle(fontSize: 12, color: MemberStyle.muted),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              sportCards(entries, current),
              const SizedBox(height: 20),
              if (current.team != null) ...[
                teamBanner(current),
                if (current.isCaptain) ...[
                  const SizedBox(height: 16),
                  captainActions(current),
                  const SizedBox(height: 24),
                  applications(current),
                ],
                const SizedBox(height: 24),
                members(current),
                const SizedBox(height: 8),
                leaveButton(current),
              ] else
                findTeams(current),
            ]);
          },
        );
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 종목 카드: 팀이 있으면 팀명·역할(팀장/팀원), 없으면 '+ 가입/개설'을 표시합니다.
  Widget sportCards(List<SportTeam> entries, SportTeam current) => Row(
    children: [
      for (final (index, entry) in entries.indexed) ...[
        if (index > 0) const SizedBox(width: 8),
        Expanded(
          child: InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: () => setState(() => selected = entry.sport),
            child: Container(
              height: 96,
              padding: const EdgeInsets.symmetric(horizontal: 6),
              decoration: BoxDecoration(
                color: entry == current
                    ? MemberStyle.greenSurface
                    : Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: entry == current
                      ? MemberStyle.green
                      : MemberStyle.line,
                  width: entry == current ? 2 : 1,
                ),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    sportIcons[entry.sport] ?? '',
                    style: const TextStyle(fontSize: 22),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    entry.team == null ? '+ 가입/개설' : '${entry.team!['t_name']}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                      color: entry.team == null
                          ? MemberStyle.blue
                          : Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    entry.team == null
                        ? sports[entry.sport]!
                        : entry.isCaptain
                        ? '팀장'
                        : '팀원',
                    style: const TextStyle(
                      fontSize: 12,
                      color: MemberStyle.muted,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    ],
  );

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 팀 배너: 팀명·종목·팀원 수와 역할, 전적 자리에는 팀 등급(팀 점수 기준)을 표시합니다.
  Widget teamBanner(SportTeam entry) {
    final team = entry.team!;
    final name = '${team['t_name']}';
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        gradient: const LinearGradient(
          colors: [Color(0xFF0B8A3E), MemberStyle.green],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 60,
                height: 60,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(
                  name.characters.take(2).toString().toUpperCase(),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${sportIcons[entry.sport]} ${sports[entry.sport]} · 팀원 ${team['member_count'] ?? 0}명',
                      style: const TextStyle(color: Colors.white),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              bannerChip(
                entry.isCaptain
                    ? '👑 팀장 (나)'
                    : '팀장 ${team['captain_name'] ?? '미등록'}',
              ),
              if (!entry.isCaptain) bannerChip('팀원 (나)'),
              bannerChip('등급 ${team['tier'] ?? '-'}'),
            ],
          ),
        ],
      ),
    );
  }

  Widget bannerChip(String text) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: 0.18),
      borderRadius: BorderRadius.circular(6),
    ),
    child: Text(
      text,
      style: const TextStyle(
        color: Colors.white,
        fontSize: 12,
        fontWeight: FontWeight.w700,
      ),
    ),
  );

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 팀장 전용 버튼: 기존 게시판(팀원모집)·팀 매칭·채팅 화면으로 연결합니다.
  Widget captainActions(SportTeam entry) => Row(
    children: [
      for (final (index, (label, onTap)) in [
        (
          '팀원 모집',
          () => openAs(entry.sport, const BoardPage(initialCategory: '팀원모집')),
        ),
        ('경기 매칭', () => openAs(entry.sport, const TeamMatchPostPage())),
        ('팀 채팅', () => openTeamChat(entry)),
      ].indexed) ...[
        if (index > 0) const SizedBox(width: 8),
        Expanded(
          child: OutlinedButton(
            onPressed: busy ? null : onTap,
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ),
      ],
    ],
  );

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 가입 신청 관리(팀장 전용): 기존 /team/applications 중 대기 상태만 보여주고 승인·거절합니다.
  Widget applications(SportTeam entry) {
    final teamId = entry.team!['t_id'] as int;
    final action = recruitmentActionProvider((
      seq: 0,
      id: entry.memberId,
      teamId: teamId,
    ));
    // 수정 일 : 2026-10-31 / 작업자 : 신현진 — AsyncNotifier 변환으로 처리 중 여부는 isLoading
    final working = ref.watch(action).isLoading;
    return ApiContent(
      query: apiQuery('/team/applications/$teamId', {
        'c_id_seq': entry.memberId,
      }),
      builder: (data) {
        final waiting = apiRows(data)
            .where((row) => row['tr_state'] == '대기')
            .toList();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  '가입 신청 ${waiting.length}건',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const Spacer(),
                MemberStatusBadge(
                  '팀장 전용',
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ],
            ),
            if (waiting.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  '대기 중인 가입 신청이 없습니다.',
                  style: TextStyle(color: MemberStyle.muted),
                ),
              ),
            for (final row in waiting)
              personTile(
                name: '${row['c_name'] ?? row['c_id_seq']}',
                subtitle: '${row['c_id_seq']} · 신청 ${row['tr_date'] ?? ''}',
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (final (label, kind) in [
                      ('승인', 'approve'),
                      ('거절', 'reject'),
                    ])
                      Padding(
                        padding: const EdgeInsets.only(left: 6),
                        child: TextButton(
                          onPressed: working
                              ? null
                              : () async {
                                  try {
                                    await ref
                                        .read(action.notifier)
                                        .submit(
                                          teamId,
                                          kind,
                                          applicant: '${row['c_id_seq']}',
                                        );
                                  } catch (error) {
                                    if (mounted) showMessage(context, error);
                                  }
                                },
                          child: Text(label),
                        ),
                      ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 팀원 목록: 팀장·팀원 모두 볼 수 있으며 팀장이 맨 위, 이름·등급·포지션을 표시합니다.
  Widget members(SportTeam entry) => ref
      .watch(teamMembersProvider(entry.team!['t_id'] as int))
      .when(
        loading: () => const Padding(
          padding: EdgeInsets.all(24),
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (error, _) => Column(
          children: [
            Text('$error'.replaceFirst('Exception: ', '')),
            TextButton(
              onPressed: () => ref.invalidate(teamMembersProvider),
              child: const Text('팀원 다시 조회'),
            ),
          ],
        ),
        data: (rows) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '팀원 ${rows.length}명',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
            ),
            for (final row in rows)
              personTile(
                name:
                    '${row['c_name'] ?? row['c_id_seq']}${row['is_me'] == true ? ' (나)' : ''}',
                subtitle: [
                  if (row['tier'] != null) '${row['tier']}',
                  if ('${row['c_position'] ?? ''}'.isNotEmpty)
                    '${row['c_position']}',
                ].join(' · '),
                trailing: row['is_captain'] == true
                    ? const MemberStatusBadge('팀장', color: MemberStyle.green)
                    : null,
              ),
          ],
        ),
      );

  Widget personTile({
    required String name,
    required String subtitle,
    Widget? trailing,
  }) => Container(
    decoration: const BoxDecoration(
      border: Border(bottom: BorderSide(color: MemberStyle.line)),
    ),
    child: ListTile(
      contentPadding: EdgeInsets.zero,
      leading: CircleAvatar(
        backgroundColor: MemberStyle.blue,
        child: Text(
          name.characters.first,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
      title: Text(name, style: const TextStyle(fontWeight: FontWeight.w800)),
      subtitle: subtitle.isEmpty ? null : Text(subtitle),
      trailing: trailing,
    ),
  );

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 팀원은 탈퇴, 팀장은 팀 폐지(팀장은 서버 규칙상 탈퇴 불가)를 해당 종목 회원 ID로 요청합니다.
  Widget leaveButton(SportTeam entry) {
    final teamId = entry.team!['t_id'];
    return Align(
      alignment: Alignment.centerRight,
      child: TextButton(
        onPressed: busy
            ? null
            : () => run(
                () => ref
                    .read(memberApiProvider)
                    .request(
                      entry.isCaptain
                          ? '/team/delete/$teamId'
                          : '/team/leave/$teamId',
                      method: 'DELETE',
                      query: {'c_id_seq': entry.memberId},
                    ),
                confirm: entry.isCaptain ? '팀 폐지' : '팀 탈퇴',
                done: entry.isCaptain ? '팀이 폐지되었습니다.' : '팀에서 탈퇴했습니다.',
              ),
        style: TextButton.styleFrom(foregroundColor: MemberStyle.muted),
        child: Text(entry.isCaptain ? '팀 폐지' : '팀 탈퇴'),
      ),
    );
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 팀이 없는 종목: 가입 대기 안내 → 팀 개설 → 같은 종목의 팀 목록(가입 신청)을 보여줍니다.
  Widget findTeams(SportTeam entry) {
    final pendingIds = {for (final p in entry.pending) p['t_id']};
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '${sports[entry.sport]} 소속 팀이 없습니다',
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 6),
        const Text(
          '팀을 개설하면 팀장이 됩니다. 팀장이 승인한 후 가입이 완료됩니다.',
          style: TextStyle(color: MemberStyle.muted),
        ),
        for (final p in entry.pending)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: MemberStatusBadge('${p['t_name']} 가입 승인 대기 중'),
          ),
        const SizedBox(height: 14),
        FilledButton.icon(
          onPressed: busy
              ? null
              : () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute<void>(
                      builder: (_) => TeamCreatePage(sport: entry.sport),
                    ),
                  );
                  if (mounted) ref.invalidate(teamDataRefreshProvider);
                },
          icon: const Icon(Icons.group_add_outlined),
          label: const Text('팀 개설'),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: search,
          maxLength: 50,
          decoration: const InputDecoration(
            labelText: '팀 이름 검색',
            suffixIcon: Icon(Icons.search),
          ),
          onSubmitted: (v) => setState(() => keyword = v.trim()),
        ),
        ApiContent(
          query: listQuery,
          builder: (data) => FeedItems(
            // 같은 종목(개설자 ID 끝자리)의 운영 중인 팀만 남깁니다.
            data: {
              ...data,
              'results': apiRows(data)
                  .where((row) => teamSport(row) == entry.sport)
                  .toList(),
            },
            item: (row) => Card(
              child: ListTile(
                contentPadding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
                leading: CircleAvatar(
                  backgroundColor: MemberStyle.greenSurface,
                  child: Text(sportIcons[entry.sport] ?? ''),
                ),
                title: Text(
                  '${row['t_name']}',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                subtitle: Text(
                  '팀장 ${row['captain_name'] ?? '미등록'} · ${row['member_count'] ?? 0}명',
                ),
                // 팀 상세의 가입 버튼도 이 종목 회원 ID를 쓰도록 종목을 맞춰 이동합니다.
                onTap: () =>
                    openAs(entry.sport, TeamDetailPage(id: row['t_id'] as int)),
                trailing: pendingIds.contains(row['t_id'])
                    ? const MemberStatusBadge('신청 대기')
                    : TextButton(
                        onPressed: busy
                            ? null
                            : () => run(
                                () => ref
                                    .read(memberApiProvider)
                                    .request(
                                      '/team/apply/${row['t_id']}',
                                      body: {'c_id_seq': entry.memberId},
                                    ),
                                confirm: '팀 가입',
                                done: '가입 신청이 완료되었습니다. 팀장 승인을 기다려 주세요.',
                              ),
                        child: const Text('가입 신청'),
                      ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (팀 탭 목업 적용·전 종목 소속팀·선호종목 기준 개설·가입)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (테마 대비 적용)
// 최종 수정 일 : 2026-10-31 / 작업자 : 신현진 (동작 Notifier AsyncNotifier 변환에 맞춰 isLoading 사용)
