// 2026-10-27
// 작업자 : 양태건
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../../vm/board_state.dart';
import '../shared/member_style.dart';
import 'board_widgets.dart';
import 'board_match_card.dart';
import 'board_recruitment_card.dart';
import '../shared/api_content.dart';
import '../shared/ui.dart';
import 'board_editor.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 부모 없는 최초 댓글과 모든 깊이의 대댓글을 동일 API로 처리합니다.
class BoardDetailPage extends ConsumerStatefulWidget {
  const BoardDetailPage({super.key, required this.seq});
  final int seq;
  @override
  ConsumerState<BoardDetailPage> createState() => _BoardDetailPageState();
}

class _BoardDetailPageState extends ConsumerState<BoardDetailPage> {
  bool busy = false;
  bool sending = false;
  final replyText = TextEditingController();
  @override
  void dispose() {
    replyText.dispose();
    super.dispose();
  }

  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  // 하단 입력은 최초 댓글을 부모 없이 전송하고 실패 시 내용을 보존합니다.
  Future<void> sendComment() async {
    if (sending || replyText.text.trim().isEmpty) return;
    final id = ref.read(memberIdProvider);
    final text = replyText.text.trim();
    setState(() => sending = true);
    try {
      await ref
          .read(memberApiProvider)
          .request(
            '/board/comment/insert/${widget.seq}',
            body: {'c_id_seq': id, 'comment_content': text},
          );
      if (!mounted) return;
      replyText.clear();
      refreshBoardThread(ref, widget.seq);
    } catch (error) {
      if (mounted) {
        refreshBoardThread(ref, widget.seq);
        showMessage(context, error);
      }
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  ApiQuery get post => apiQuery('/board/select/${widget.seq}');
  ApiQuery get comments => apiQuery('/board/comment/select/${widget.seq}');
  Future<void> edit(
    Map<String, dynamic> row, {
    bool comment = false,
    bool reply = false,
  }) async {
    final id = ref.read(memberIdProvider);
    await showDialog<bool>(
      context: context,
      builder: (_) => BoardEditor(
        initial: reply ? const {} : row,
        comment: comment,
        save: (body) async {
          final creating = reply || row.isEmpty;
          final path = comment
              ? creating
                    ? '/board/comment/insert/${widget.seq}'
                    : '/board/comment/update/${row['comment_seq']}'
              : '/board/update/${widget.seq}';
          await ref
              .read(memberApiProvider)
              .request(
                path,
                method: comment && creating ? 'POST' : 'PUT',
                query: comment && !creating
                    ? {'bulletin_seq': '${widget.seq}'}
                    : null,
                body: {
                  ...body,
                  'c_id_seq': id,
                  if (reply) 'reply_to_comment_seq': row['comment_seq'],
                },
              );
          if (!mounted) return;
          if (comment) {
            refreshBoardThread(ref, widget.seq);
          } else {
            ref.invalidate(apiDocumentProvider(post));
          }
        },
      ),
    );
  }

  Future<void> remove([Map<String, dynamic>? row]) async {
    if (busy) return;
    setState(() => busy = true);
    final id = ref.read(memberIdProvider);
    try {
      final ok = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(row == null ? '게시글 삭제' : '댓글 삭제'),
          content: const Text('삭제하시겠어요?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('돌아가기'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('삭제'),
            ),
          ],
        ),
      );
      if (ok != true || !mounted) return;
      await ref
          .read(memberApiProvider)
          .request(
            row == null
                ? '/board/delete/${widget.seq}'
                : '/board/comment/delete/${row['comment_seq']}',
            method: 'DELETE',
            query: {
              'c_id_seq': id,
              if (row != null) 'bulletin_seq': '${widget.seq}',
            },
          );
      if (!mounted) return;
      if (row == null) {
        Navigator.pop(context);
      } else {
        refreshBoardThread(ref, widget.seq);
      }
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  // 작성자·본문·실제 조회/댓글 수·연결 경기·계층 댓글을 목업 스타일로 표시합니다.
  @override
  Widget build(BuildContext context) {
    final id = ref.watch(memberIdProvider);
    final writable = ref.watch(boardCommentWritableProvider(widget.seq));
    final canComment = writable.asData?.value == true;
    final postValue = ref.watch(apiDocumentProvider(post)).asData?.value;
    final commentValue = ref.watch(apiDocumentProvider(comments)).asData?.value;
    final own = postValue?['c_id_seq'] == id;
    final sport = '${postValue?['event_category'] ?? ''}';
    final emoji =
        {
          for (final entry in sports.entries)
            entry.value: boardEmoji[entry.key],
        }[sport] ??
        '';
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: Text(
          '$emoji $sport 게시판',
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
        ),
        actions: [
          if (own)
            PopupMenuButton<String>(
              tooltip: '게시글 메뉴',
              enabled: !busy,
              onSelected: (value) {
                if (value == 'edit') edit(postValue!);
                if (value == 'delete') remove();
              },
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'edit', child: Text('글 수정')),
                PopupMenuItem(value: 'delete', child: Text('글 삭제')),
              ],
            ),
        ],
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(height: 1),
        ),
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Container(
          padding: EdgeInsets.fromLTRB(
            12,
            10,
            12,
            10 + MediaQuery.viewInsetsOf(context).bottom,
          ),
          decoration: const BoxDecoration(
            color: Colors.white,
            border: Border(top: BorderSide(color: MemberStyle.line)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  key: const ValueKey('boardCommentInput'),
                  controller: replyText,
                  enabled: canComment && !sending,
                  minLines: 1,
                  maxLines: 4,
                  maxLength: 5000,
                  decoration: InputDecoration(
                    hintText: canComment
                        ? '${ref.watch(sessionProvider)?['c_name'] ?? '회원'}(으)로 댓글 남기기'
                        : writable.isLoading
                        ? '작성 가능 여부 확인 중…'
                        : writable.hasError
                        ? '작성 가능 여부를 다시 확인해 주세요.'
                        : '매칭 성사로 댓글 작성이 종료되었습니다.',
                    filled: true,
                    fillColor: MemberStyle.surface,
                    counterText: '',
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 14,
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(16),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
              ),
              TextButton(
                onPressed: !canComment || sending ? null : sendComment,
                child: Text(
                  sending ? '등록 중…' : '등록',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
        ),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 900),
          child: ListView(
            padding: EdgeInsets.zero,
            children: [
              ApiContent(
                query: post,
                builder: (row) => Padding(
                  padding: const EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          BoardAvatar('${row['c_name'] ?? '회원'}', author: true),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '${row['c_name'] ?? '회원'}',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w800,
                                    fontSize: 15,
                                  ),
                                ),
                                const SizedBox(height: 3),
                                Text(
                                  boardDateLabel(row['board_date']),
                                  style: const TextStyle(
                                    color: MemberStyle.muted,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 22),
                      BoardCategoryBadge('${row['board_category']}'),
                      const SizedBox(height: 10),
                      Text(
                        '${row['board_title']}',
                        style: const TextStyle(
                          fontSize: 21,
                          fontWeight: FontWeight.w800,
                          color: MemberStyle.ink,
                          height: 1.5,
                        ),
                      ),
                      const SizedBox(height: 20),
                      SelectableText(
                        '${row['board_content'] ?? ''}'.replaceFirst(
                          RegExp(r'^\[예약번호:\d+\]\s*'),
                          '',
                        ),
                        style: const TextStyle(
                          fontSize: 15,
                          height: 1.85,
                          color: MemberStyle.ink,
                        ),
                      ),
                      const SizedBox(height: 20),
                      Wrap(
                        spacing: 16,
                        children: [
                          if (commentValue != null)
                            Text(
                              '댓글 ${apiRows(commentValue).length}',
                              style: const TextStyle(
                                color: Color(0xFF08AAB8),
                                fontSize: 12,
                              ),
                            ),
                          if (row['board_views'] != null)
                            Text(
                              '조회 ${row['board_views']}',
                              style: const TextStyle(
                                color: MemberStyle.muted,
                                fontSize: 12,
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              if (postValue != null && boardReservationId(postValue) != null)
                BoardMatchCard(seq: widget.seq),
              // 수정 일 : 2026-10-28 / 작업자 : 양태건
              if (postValue?['board_category'] == '팀원모집')
                BoardRecruitmentCard(
                  seq: widget.seq,
                  sport: '${postValue?['event_category']}',
                ),
              Container(height: 8, color: MemberStyle.surface),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        '댓글${commentValue == null ? '' : ' ${apiRows(commentValue).length}'}',
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                    ),
                  ],
                ),
              ),
              if (writable.hasError)
                TextButton(
                  onPressed: () => refreshBoardThread(ref, widget.seq),
                  child: const Text('댓글 작성 가능 여부 다시 확인'),
                ),
              if (writable.asData?.value == false)
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('매칭이 성사되어 댓글 작성이 종료되었습니다.'),
                ),
              ApiContent(
                query: comments,
                builder: (data) => FeedItems(
                  data: data,
                  item: (row) {
                    final deleted =
                        row['comment_delete_state'] == true ||
                        row['comment_delete_state'] == 1;
                    final depth = (row['depth'] as num? ?? 0).toDouble();
                    final author = row['c_id_seq'] == postValue?['c_id_seq'];
                    return Container(
                      padding: EdgeInsets.fromLTRB(
                        16 + math.min(depth, 4) * 12,
                        16,
                        16,
                        8,
                      ),
                      decoration: BoxDecoration(
                        color: depth > 0
                            ? const Color(0xFFFAFBFD)
                            : Colors.white,
                        border: const Border(
                          bottom: BorderSide(color: MemberStyle.line),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              BoardAvatar('${row['c_name'] ?? '회원'}'),
                              const SizedBox(width: 9),
                              Expanded(
                                child: Text(
                                  '${depth > 0 ? '↳ ' : ''}${row['c_name'] ?? '회원'}${author ? ' · 글쓴이' : ''}',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w800,
                                    color: author
                                        ? const Color(0xFF08AAB8)
                                        : MemberStyle.ink,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 9),
                          Text(
                            deleted
                                ? '삭제된 댓글입니다.'
                                : '${row['comment_content']}',
                            style: const TextStyle(
                              fontSize: 14,
                              height: 1.6,
                              color: MemberStyle.ink,
                            ),
                          ),
                          Wrap(
                            children: [
                              if (!deleted)
                                TextButton(
                                  onPressed: busy || !canComment
                                      ? null
                                      : () => edit(
                                          row,
                                          comment: true,
                                          reply: true,
                                        ),
                                  child: const Text(
                                    '답글',
                                    style: TextStyle(fontSize: 11),
                                  ),
                                ),
                              if (!deleted && row['c_id_seq'] == id) ...[
                                TextButton(
                                  onPressed: busy
                                      ? null
                                      : () => edit(row, comment: true),
                                  child: const Text(
                                    '수정',
                                    style: TextStyle(fontSize: 11),
                                  ),
                                ),
                                TextButton(
                                  onPressed: busy ? null : () => remove(row),
                                  child: const Text(
                                    '삭제',
                                    style: TextStyle(fontSize: 11),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
