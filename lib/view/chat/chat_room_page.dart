// 2026-10-27
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/chat_state.dart';
import '../../vm/member_state.dart';
import '../shared/ui.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 전체 회원 목업의 화면 흐름과 공통 스타일을 적용합니다.

class ChatRoomPage extends ConsumerStatefulWidget {
  const ChatRoomPage({super.key, required this.room});
  final Map<String, dynamic> room;
  @override
  ConsumerState<ChatRoomPage> createState() => _ChatRoomPageState();
}

class _ChatRoomPageState extends ConsumerState<ChatRoomPage> {
  final message = TextEditingController();
  final invite = TextEditingController();
  bool busy = false;
  int get id => widget.room['me_id'] as int;
  @override
  void dispose() {
    message.dispose();
    invite.dispose();
    super.dispose();
  }

  Future<void> action({bool inviting = false}) async {
    if (busy) return;
    final owner = widget.room['owner_id'] == ref.read(memberIdProvider);
    setState(() => busy = true);
    try {
      final ok = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(
            inviting
                ? '회원 초대'
                : owner
                ? '채팅방 종료'
                : '채팅방 나가기',
          ),
          content: inviting
              ? TextField(
                  controller: invite,
                  decoration: const InputDecoration(
                    labelText: '종목별 회원 ID',
                    hintText: '예: member_01',
                  ),
                )
              : const Text('진행하시겠어요?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('돌아가기'),
            ),
            FilledButton(
              onPressed: () {
                if (!inviting || invite.text.trim().isNotEmpty) {
                  Navigator.pop(context, true);
                }
              },
              child: const Text('확인'),
            ),
          ],
        ),
      );
      if (ok != true || !mounted) return;
      await ref
          .read(memberApiProvider)
          .request(
            inviting
                ? '/chat/rooms/$id/invite'
                : '/chat/rooms/$id${owner ? '' : '/leave'}',
            method: inviting ? 'POST' : 'DELETE',
            body: inviting
                ? {
                    'member_ids': [invite.text.trim()],
                  }
                : null,
            accessToken: ref.read(chatTokenProvider),
          );
      if (!mounted) return;
      if (inviting) {
        invite.clear();
        showMessage(context, '초대되었습니다.');
      } else {
        Navigator.pop(context);
      }
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final token = ref.watch(chatTokenProvider);
    final owner = widget.room['owner_id'] == ref.watch(memberIdProvider);
    final state = token == null ? null : ref.watch(chatMessagesProvider(id));
    ref.listen(chatMessagesProvider(id), (previous, next) {
      final old = previous?.asData?.value;
      final value = next.asData?.value;
      if (value?.confirmedId != null &&
          value!.confirmedId != old?.confirmedId) {
        final confirmed = value.messages.firstWhere(
          (m) => m['s_me_id'] == value.confirmedId,
        );
        if (message.text.trim() == confirmed['s_me_content']) message.clear();
      }
    });
    final snapshot = state?.asData?.value;
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.room['me_name']}'),
        actions: [
          if (owner)
            IconButton(
              tooltip: '회원 초대',
              onPressed: busy || token == null
                  ? null
                  : () => action(inviting: true),
              icon: const Icon(Icons.person_add_outlined),
            ),
          IconButton(
            tooltip: owner ? '방 종료' : '나가기',
            onPressed: busy || token == null ? null : () => action(),
            icon: const Icon(Icons.exit_to_app),
          ),
        ],
      ),
      body: Column(
        children: [
          ListTile(
            title: Text(
              token == null
                  ? '채팅 인증이 필요합니다. 목록으로 돌아가 다시 로그인해 주세요.'
                  : snapshot?.notice ?? '메시지 연결 중…',
            ),
            trailing: IconButton(
              tooltip: '다시 연결',
              onPressed: token == null
                  ? null
                  : () {
                      ref.invalidate(chatConnectionProvider(id));
                    },
              icon: const Icon(Icons.refresh),
            ),
          ),
          if (snapshot?.hasOlder == true)
            TextButton(
              onPressed: () => ref.read(chatConnectionProvider(id)).loadOlder(),
              child: const Text('이전 메시지'),
            ),
          Expanded(
            child: ListView.builder(
              reverse: true,
              padding: const EdgeInsets.all(16),
              itemCount: snapshot?.messages.length ?? 0,
              itemBuilder: (context, index) {
                final row =
                    snapshot!.messages[snapshot.messages.length - 1 - index];
                final mine = row['c_id_seq'] == ref.watch(memberIdProvider);
                return Align(
                  alignment: mine
                      ? Alignment.centerRight
                      : Alignment.centerLeft,
                  child: Container(
                    constraints: const BoxConstraints(maxWidth: 320),
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: mine
                          ? const Color(0xFF8B4DFF)
                          : const Color(0xFFF1F3F6),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${row['c_name'] ?? '회원'}',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: mine
                                ? Colors.white
                                : const Color(0xFF141A24),
                          ),
                        ),
                        Text(
                          '${row['s_me_content']}',
                          style: TextStyle(
                            color: mine
                                ? Colors.white
                                : const Color(0xFF141A24),
                          ),
                        ),
                        Text(
                          '${row['s_me_date'] ?? ''}',
                          style: Theme.of(context).textTheme.labelSmall
                              ?.copyWith(
                                color: mine
                                    ? Colors.white70
                                    : const Color(0xFF757D8E),
                              ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: TextField(
                      controller: message,
                      maxLength: 10000,
                      minLines: 1,
                      maxLines: 4,
                      enabled: snapshot?.pending == null,
                      decoration: const InputDecoration(
                        hintText: '메시지 입력',
                        counterText: '',
                      ),
                    ),
                  ),
                  IconButton(
                    tooltip: '메시지 보내기',
                    onPressed:
                        snapshot?.ready == true && snapshot?.pending == null
                        ? () => ref
                              .read(chatConnectionProvider(id))
                              .send(message.text)
                        : null,
                    icon: const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
