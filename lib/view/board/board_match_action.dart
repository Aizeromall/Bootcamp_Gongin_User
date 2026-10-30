// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../../vm/board_state.dart';
import '../shared/api_content.dart';
import '../shared/member_style.dart';
import '../shared/ui.dart';
import '../shared/team_lineup_picker.dart';
import 'board_match_card.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 목록에서는 조회 수를 올리는 상세 API를 호출하지 않고 팀매칭 목록의 신청 상태를 사용합니다.
class BoardMatchAction extends ConsumerStatefulWidget {
  const BoardMatchAction({super.key, required this.post});
  final Map<String, dynamic> post;
  @override
  ConsumerState<BoardMatchAction> createState() => _BoardMatchActionState();
}

class _BoardMatchActionState extends ConsumerState<BoardMatchAction> {
  bool busy = false;
  List<String> lineup = [];
  int get seq => widget.post['bulletin_seq'] as int;
  Future<void> request(String id, ApiQuery query) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      final session = ref.read(sessionProvider);
      final token = session?['access_token'];
      if (token is! String || token.isEmpty) throw Exception('다시 로그인해 주세요.');
      final chosen = await selectTeamLineup(
        context,
        query: (memberId: id, rentalId: null, postId: seq),
        initial: lineup,
      );
      if (chosen == null ||
          !mounted ||
          !identical(session, ref.read(sessionProvider))) {
        return;
      }
      lineup = chosen;
      await ref
          .read(memberApiProvider)
          .request(
            '/team_match/request',
            body: {'c_id_seq': id, 'bulletin_seq': seq, 'member_ids': lineup},
            accessToken: token,
          );
      if (!mounted) return;
      ref.invalidate(apiDocumentProvider(query));
      ref.invalidate(boardMatchInfoProvider(seq));
      ref.invalidate(
        apiDocumentProvider(apiQuery('/board/comment/select/$seq')),
      );
      showMessage(context, '매칭을 신청했습니다. 상대 팀장의 응답을 기다려 주세요.');
    } catch (error) {
      if (mounted) {
        ref.invalidate(apiDocumentProvider(query));
        showMessage(context, error);
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> received(String id) async {
    if (busy) return;
    setState(() => busy = true);
    ref.invalidate(
      apiDocumentProvider(
        apiQuery('/team_match/requests/$seq', {'c_id_seq': id}),
      ),
    );
    ref.invalidate(boardMatchInfoProvider(seq));
    try {
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        showDragHandle: true,
        backgroundColor: Theme.of(context).colorScheme.surface,
        constraints: const BoxConstraints(maxWidth: 650),
        builder: (context) => FractionallySizedBox(
          heightFactor: 0.78,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 0, 8, 8),
                child: Row(
                  children: [
                    const Expanded(
                      child: Text(
                        '신청 목록',
                        style: TextStyle(
                          fontSize: 19,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    IconButton(
                      tooltip: '신청 목록 닫기',
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: SingleChildScrollView(
                  child: ApiContent(
                    query: apiQuery('/board/select/$seq'),
                    builder: (post) => boardReservationId(post) == null
                        ? const Padding(
                            padding: EdgeInsets.all(24),
                            child: Text(
                              '구장 대여와 연결된 매칭신청 글에서 신청 목록을 확인할 수 있습니다.',
                            ),
                          )
                        : BoardMatchCard(seq: seq),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget button(String text, VoidCallback? action, {String? hint}) {
    final child = SizedBox(
      width: 86,
      child: FilledButton(
        style: FilledButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
          minimumSize: const Size(0, 42),
          backgroundColor: MemberStyle.blue,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
        onPressed: busy ? null : action,
        child: Text(
          busy ? '처리 중…' : text,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800),
        ),
      ),
    );
    return hint == null ? child : Tooltip(message: hint, child: child);
  }

  @override
  Widget build(BuildContext context) {
    final id = boardMemberId(
      ref.watch(sessionProvider),
      '${widget.post['event_category']}',
    );
    if (id == null) {
      return button('매칭신청', null, hint: '이 종목으로 가입한 팀장이 신청할 수 있습니다.');
    }
    if (id == widget.post['c_id_seq']) {
      return button('신청 목록', () => received(id));
    }
    final query = apiQuery('/team_match/posts', {'c_id_seq': id});
    return ref
        .watch(apiDocumentProvider(query))
        .when(
          loading: () => const SizedBox(
            width: 86,
            height: 42,
            child: Center(
              child: SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
          ),
          error: (_, _) => SizedBox(
            width: 86,
            child: TextButton(
              onPressed: () => ref.invalidate(apiDocumentProvider(query)),
              child: const Text('다시 확인'),
            ),
          ),
          data: (data) {
            Map<String, dynamic>? match;
            for (final row in apiRows(data)) {
              if (row['bulletin_seq'] == seq) match = row;
            }
            final status = match?['status'];
            if (status == 'requested') {
              return button('신청 완료', null, hint: '상대 팀장의 수락·거절을 기다리는 중입니다.');
            }
            if (status == 'accepted') return button('매칭 성사', null);
            final eligible = data['can_request'] == true && match != null;
            return button(
              status == 'rejected' ? '다시 신청' : '매칭신청',
              eligible ? () => request(id, query) : null,
              hint: eligible
                  ? null
                  : '구장 대여가 연결된 신청 가능한 경기에서 다른 팀 팀장만 신청할 수 있습니다.',
            );
          },
        );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (테마 대비 적용)
