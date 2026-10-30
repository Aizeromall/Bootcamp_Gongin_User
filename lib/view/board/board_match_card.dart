// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/board_state.dart';
import '../../vm/member_features.dart';
import '../shared/member_style.dart';
import '../shared/ui.dart';
import '../shared/team_lineup_picker.dart';
import 'board_widgets.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 예약번호로 연결된 매칭신청 글에만 실제 경기·신청 상태를 표시합니다.
class BoardMatchCard extends ConsumerStatefulWidget {
  const BoardMatchCard({super.key, required this.seq});
  final int seq;
  @override
  ConsumerState<BoardMatchCard> createState() => _BoardMatchCardState();
}

class _BoardMatchCardState extends ConsumerState<BoardMatchCard> {
  bool busy = false;
  List<String> lineup = [];
  Future<void> act(String path, String id, {int? comment}) async {
    if (busy) return;
    final session = ref.read(sessionProvider);
    setState(() => busy = true);
    try {
      final token = session?['access_token'];
      if (token is! String || token.isEmpty) throw Exception('다시 로그인해 주세요.');
      var ok = false;
      if (path.endsWith('request')) {
        final chosen = await selectTeamLineup(
          context,
          query: (memberId: id, rentalId: null, postId: widget.seq),
          initial: lineup,
        );
        if (chosen != null) {
          lineup = chosen;
          ok = true;
        }
      } else {
        ok =
            await showDialog<bool>(
              context: context,
              builder: (context) => AlertDialog(
                title: Text(
                  path.endsWith('request')
                      ? '매칭 신청'
                      : path.endsWith('accept')
                      ? '매칭 승인'
                      : '매칭 거절',
                ),
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
            ) ??
            false;
      }
      if (!ok || !mounted || !identical(session, ref.read(sessionProvider))) {
        return;
      }
      await ref
          .read(memberApiProvider)
          .request(
            path,
            body: {
              'c_id_seq': id,
              'bulletin_seq': widget.seq,
              'comment_seq': ?comment,
              if (path.endsWith('request')) 'member_ids': lineup,
            },
            accessToken: token,
          );
      if (!mounted || !identical(session, ref.read(sessionProvider))) return;
      refreshBoardThread(ref, widget.seq);
      showMessage(context, '매칭 정보가 변경되었습니다.');
    } catch (error) {
      if (mounted && identical(session, ref.read(sessionProvider))) {
        refreshBoardThread(ref, widget.seq);
        showMessage(context, error);
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => ref
      .watch(boardMatchInfoProvider(widget.seq))
      .when(
        loading: () => const Padding(
          padding: EdgeInsets.all(16),
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (error, _) => Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Text('$error'),
              TextButton(
                onPressed: () => refreshBoardThread(ref, widget.seq),
                child: const Text('매칭 정보 다시 확인'),
              ),
            ],
          ),
        ),
        data: (info) {
          if (info == null) return const SizedBox.shrink();
          final reservation = info['reservation'] as Map<String, dynamic>;
          final match = info['match'] as Map<String, dynamic>?;
          final post = ref
              .watch(
                apiDocumentProvider(apiQuery('/board/select/${widget.seq}')),
              )
              .asData
              ?.value;
          final id = info['member_id'] as String?;
          final own = info['own'] == true;
          final matched =
              reservation['r_check'] == true || reservation['r_check'] == 1;
          final canceled = '${reservation['r_category']}' == '2';
          final status = '${match?['status'] ?? 'none'}';
          final eligible =
              info['can_request'] == true &&
              !matched &&
              !canceled &&
              status != 'requested' &&
              status != 'accepted';
          final requests = (info['requests'] as List)
              .cast<Map<String, dynamic>>()
              .where(
                (r) =>
                    r['status'] != 'none' &&
                    r['t_id'] != null &&
                    r['c_id_seq'] != id,
              );
          return Container(
            margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: MemberStyle.surface,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: MemberStyle.line),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    BoardAvatar('${match?['t_name'] ?? '경기'}', author: true),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${match?['t_name'] ?? '예약 경기'}',
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              fontSize: 16,
                            ),
                          ),
                          Text(
                            '${post?['event_category'] ?? ''} · ${reservation['r_date'] ?? ''}',
                            style: const TextStyle(
                              fontSize: 12,
                              color: MemberStyle.muted,
                            ),
                          ),
                          Text(
                            '${reservation['g_name'] ?? ''} · ${reservation['rs_time'] ?? ''} ~ ${reservation['re_time'] ?? ''}',
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
                if (!own)
                  FilledButton(
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.fromHeight(52),
                      backgroundColor: MemberStyle.blue,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    onPressed: busy || !eligible || id == null
                        ? null
                        : () => act('/team_match/request', id),
                    child: Text(
                      matched
                          ? '매칭 성사'
                          : canceled
                          ? '취소된 경기'
                          : status == 'requested'
                          ? '신청 완료 · 응답 대기'
                          : status == 'accepted'
                          ? '매칭 성사'
                          : '매칭 신청',
                    ),
                  ),
                if (!own &&
                    !eligible &&
                    !matched &&
                    !canceled &&
                    status != 'requested')
                  const Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Text(
                      '해당 종목의 팀장이 신청 가능한 경기에서 이용할 수 있습니다.',
                      style: TextStyle(fontSize: 11, color: MemberStyle.muted),
                    ),
                  ),
                if (own) ...[
                  Text(
                    matched ? '매칭이 성사되었습니다.' : '받은 매칭 신청 · ${requests.length}건',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  if (requests.isEmpty)
                    const Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: Text('아직 매칭 신청이 없습니다.'),
                    ),
                  for (final request in requests)
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
                            '${request['t_name'] ?? request['c_name'] ?? '회원'}',
                            style: const TextStyle(fontWeight: FontWeight.w700),
                          ),
                          if (request['c_name'] != null)
                            Text(
                              '신청 팀장 ${request['c_name']}',
                              style: const TextStyle(
                                fontSize: 12,
                                color: MemberStyle.muted,
                              ),
                            ),
                          if (request['member_count'] != null)
                            Text(
                              '팀원 ${request['member_count']}명',
                              style: const TextStyle(
                                fontSize: 12,
                                color: MemberStyle.muted,
                              ),
                            ),
                          Text(
                            switch (request['status']) {
                              'requested' => '신청 대기',
                              'accepted' => '수락됨',
                              'rejected' => '거절됨',
                              _ => '',
                            },
                            style: const TextStyle(
                              fontSize: 12,
                              color: MemberStyle.muted,
                            ),
                          ),
                          if (request['status'] == 'requested' &&
                              !matched &&
                              !canceled)
                            Wrap(
                              spacing: 8,
                              children: [
                                FilledButton(
                                  onPressed: busy
                                      ? null
                                      : () => act(
                                          '/team_match/accept',
                                          id!,
                                          comment:
                                              request['comment_seq'] as int,
                                        ),
                                  child: const Text('승인'),
                                ),
                                TextButton(
                                  onPressed: busy
                                      ? null
                                      : () => act(
                                          '/team_match/reject',
                                          id!,
                                          comment:
                                              request['comment_seq'] as int,
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
            ),
          );
        },
      );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
