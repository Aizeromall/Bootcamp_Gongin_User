// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/ui.dart';
import 'team_captain_dialog.dart';
import '../board/board_recruitment_card.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 실제 팀 상세와 현재 팀장 권한에 따라 가입·탈퇴·폐지를 연결합니다.

class TeamDetailPage extends ConsumerStatefulWidget {
  const TeamDetailPage({super.key, required this.id});
  final int id;
  @override
  ConsumerState<TeamDetailPage> createState() => _TeamDetailPageState();
}

class _TeamDetailPageState extends ConsumerState<TeamDetailPage> {
  bool busy = false;
  Future<void> act(String action) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      final ok = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(
            action == 'apply'
                ? '팀 가입'
                : action == 'leave'
                ? '팀 탈퇴'
                : '팀 폐지',
          ),
          content: Text(
            action == 'apply' ? '팀장이 승인한 후 가입됩니다. 신청하시겠어요?' : '진행하시겠어요?',
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
      if (ok != true || !mounted) return;
      final id = ref.read(memberIdProvider);
      await ref
          .read(memberApiProvider)
          .request(
            '/team/$action/${widget.id}',
            method: action == 'apply' ? 'POST' : 'DELETE',
            body: action == 'apply' ? {'c_id_seq': id} : null,
            query: action != 'apply' ? {'c_id_seq': id} : null,
          );
      if (!mounted) return;
      ref.invalidate(apiDocumentProvider);
      showMessage(
        context,
        action == 'apply'
            ? '가입 신청이 완료되었습니다. 팀장 승인을 기다려 주세요.'
            : '팀 정보가 변경되었습니다.',
      );
      if (action == 'delete') Navigator.pop(context);
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('팀 정보')),
    body: pageContent([
      ApiContent(
        query: apiQuery('/team/select/${widget.id}'),
        builder: (row) => Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            heading(
              '${row['t_name']}',
              row['is_closed'] == true ? '폐지된 팀' : '운영 중인 팀',
            ),
            MemberPanel(
              child: Column(
                children: [
                  MemberInfoRow('팀장', row['captain_name']),
                  MemberInfoRow('팀원 수', '${row['member_count']}명'),
                  MemberInfoRow('팀 점수', row['t_rating']),
                  MemberInfoRow('상태 날짜', row['c_date']),
                ],
              ),
            ),
            if (row['is_closed'] != true &&
                row['captain_id'] == ref.watch(memberIdProvider))
              BoardRecruitmentCard(
                seq: 0,
                sport: sports[ref.watch(sportProvider)]!,
                teamId: widget.id,
              ),
            if (row['is_closed'] != true) ...[
              FilledButton(
                onPressed: busy ? null : () => act('apply'),
                child: const Text('팀 가입 신청'),
              ),
              // 수정 일 : 2026-10-28 / 작업자 : 양태건
              // 현재 팀장에게만 위임 동작을 제공하고 서버 응답으로 권한을 다시 조회합니다.
              if (row['captain_id'] == ref.watch(memberIdProvider))
                OutlinedButton.icon(
                  icon: const Icon(Icons.manage_accounts_outlined),
                  label: const Text('팀장 위임'),
                  onPressed: busy
                      ? null
                      : () async {
                          final changed = await showDialog<bool>(
                            context: context,
                            barrierDismissible: false,
                            builder: (_) => TeamCaptainDialog(
                              transferKey: (
                                teamId: widget.id,
                                memberId: ref.read(memberIdProvider),
                              ),
                            ),
                          );
                          if (changed == true && context.mounted) {
                            showMessage(context, '팀장 위임이 완료되었습니다.');
                          }
                        },
                ),
              TextButton(
                onPressed: busy
                    ? null
                    : () => act(
                        row['captain_id'] == ref.watch(memberIdProvider)
                            ? 'delete'
                            : 'leave',
                      ),
                child: Text(
                  row['captain_id'] == ref.watch(memberIdProvider)
                      ? '팀 폐지'
                      : '팀 탈퇴',
                ),
              ),
            ],
          ],
        ),
      ),
    ]),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
