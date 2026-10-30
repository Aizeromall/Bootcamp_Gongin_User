// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/board_state.dart';
import '../../vm/member_features.dart';
import '../../vm/member_state.dart';
import '../../vm/team_state.dart';
import '../shared/api_content.dart';
import '../shared/member_style.dart';
import 'board_widgets.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 실제 소속 팀과 신청 상태를 표시하고 현재 팀장에게만 승인·거절 동작을 제공합니다.
class BoardRecruitmentCard extends ConsumerStatefulWidget {
  const BoardRecruitmentCard({
    super.key,
    required this.seq,
    required this.sport,
    this.teamId,
  });
  final int? teamId;
  final int seq;
  final String sport;
  @override
  ConsumerState<BoardRecruitmentCard> createState() =>
      _BoardRecruitmentCardState();
}

class _BoardRecruitmentCardState extends ConsumerState<BoardRecruitmentCard> {
  bool confirming = false;
  String? error;
  Future<void> act(
    RecruitmentKey key,
    int team,
    String action,
    String? applicant,
  ) async {
    // 수정 일 : 2026-10-31 / 작업자 : 신현진 — AsyncNotifier 변환으로 처리 중 여부는 isLoading
    if (confirming || ref.read(recruitmentActionProvider(key)).isLoading) {
      return;
    }
    setState(() {
      confirming = true;
      error = null;
    });
    final session = ref.read(sessionProvider);
    try {
      final ok = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(
            action == 'apply'
                ? '팀 가입 신청'
                : action == 'approve'
                ? '가입 승인'
                : '가입 거절',
          ),
          content: Text(
            action == 'apply'
                ? '팀장 승인 후 가입이 완료됩니다. 신청하시겠어요?'
                : '${applicant ?? ''} 회원의 신청을 ${action == 'approve' ? '승인' : '거절'}하시겠어요?',
          ),
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
      if (!mounted ||
          ok != true ||
          !identical(session, ref.read(sessionProvider))) {
        return;
      }
      await ref
          .read(recruitmentActionProvider(key).notifier)
          .submit(team, action, applicant: applicant);
    } catch (e) {
      if (mounted && identical(session, ref.read(sessionProvider))) {
        setState(() => error = '$e');
      }
    } finally {
      if (mounted) setState(() => confirming = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final id = boardMemberId(ref.watch(sessionProvider), widget.sport);
    if (id == null) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('해당 종목에 가입한 회원만 팀 가입을 신청할 수 있습니다.'),
      );
    }
    final key = (seq: widget.seq, id: id, teamId: widget.teamId);
    // 수정 일 : 2026-10-31 / 작업자 : 신현진 — 처리 중 여부는 isLoading
    final submitting = ref.watch(recruitmentActionProvider(key)).isLoading;
    final busy = confirming || submitting;
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: MemberStyle.line),
      ),
      child: ApiContent(
        query: apiQuery(
          widget.teamId == null
              ? '/team/recruitment/${widget.seq}'
              : '/team/applications/${widget.teamId}',
          {'c_id_seq': id},
        ),
        builder: (data) {
          final team = data['team'] as Map;
          final manage = data['can_manage'] == true;
          final closed = team['c_category'] == '폐지일';
          final rows = apiRows(data);
          final state = data['my_state'];
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  BoardAvatar('${team['t_name']}', author: true),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${team['t_name']}',
                          style: const TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 16,
                          ),
                        ),
                        Text(
                          '${widget.sport} · 팀원모집',
                          style: const TextStyle(color: MemberStyle.muted),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (error != null)
                Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              if (!manage)
                FilledButton(
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(52),
                    backgroundColor: MemberStyle.blue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                  onPressed: busy || data['can_apply'] != true
                      ? null
                      : () => act(key, team['t_id'] as int, 'apply', null),
                  child: Text(
                    closed
                        ? '폐지된 팀'
                        : state == '대기'
                        ? '신청 완료 · 승인 대기'
                        : state == '가입'
                        ? '가입된 팀'
                        : state == '거절'
                        ? '다시 신청하기'
                        : '신청하기',
                  ),
                ),
              if (manage) ...[
                Text(
                  '가입 신청 목록 · ${rows.where((r) => r['tr_state'] == '대기').length}건 대기',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const Text(
                  '같은 팀의 모집 글에서 신청 목록을 함께 관리합니다.',
                  style: TextStyle(fontSize: 12, color: MemberStyle.muted),
                ),
                if (rows.isEmpty)
                  const Padding(
                    padding: EdgeInsets.only(top: 12),
                    child: Text('아직 가입 신청이 없습니다.'),
                  ),
                for (final row in rows)
                  Container(
                    margin: const EdgeInsets.only(top: 12),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${row['c_name']} · ${row['tr_state']}',
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        Text(
                          '${row['c_id_seq']} · ${row['tr_date'] ?? ''}',
                          style: const TextStyle(
                            fontSize: 12,
                            color: MemberStyle.muted,
                          ),
                        ),
                        if (row['tr_state'] == '대기')
                          Wrap(
                            spacing: 8,
                            children: [
                              FilledButton(
                                onPressed: busy
                                    ? null
                                    : () => act(
                                        key,
                                        team['t_id'] as int,
                                        'approve',
                                        '${row['c_id_seq']}',
                                      ),
                                child: const Text('승인'),
                              ),
                              TextButton(
                                onPressed: busy
                                    ? null
                                    : () => act(
                                        key,
                                        team['t_id'] as int,
                                        'reject',
                                        '${row['c_id_seq']}',
                                      ),
                                child: const Text('거절'),
                              ),
                            ],
                          ),
                      ],
                    ),
                  ),
              ],
            ],
          );
        },
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (테마 대비 적용)
// 최종 수정 일 : 2026-10-31 / 작업자 : 신현진 (동작 Notifier AsyncNotifier 변환에 맞춰 isLoading 사용)
