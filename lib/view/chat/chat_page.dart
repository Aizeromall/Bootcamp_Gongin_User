// 2026-10-27
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../../vm/chat_state.dart';
import '../../service/member_api.dart';
import '../shared/ui.dart';
import 'chat_room_page.dart';

class ChatPage extends ConsumerStatefulWidget {
  const ChatPage({super.key});
  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  final password = TextEditingController();
  bool busy = false;
  int offset = 0;
  String get roomsPath => '/chat/rooms?limit=20&offset=$offset';
  // MemberApi는 path의 query를 별도 인자로 다루므로 방 목록은 명시적인 provider를 사용합니다.
  @override
  void dispose() {
    password.dispose();
    super.dispose();
  }

  Future<void> login() async {
    final sessionToken = ref.read(sessionProvider)?['access_token'] as String?;
    if (busy || (sessionToken == null && password.text.isEmpty)) return;
    final id = ref.read(memberIdProvider);
    setState(() => busy = true);
    try {
      final result = await ref
          .read(memberApiProvider)
          .request(
            sessionToken == null ? '/chat/token' : '/chat/session-token',
            body: {
              'c_id_seq': id,
              if (sessionToken == null) 'c_pw': password.text,
            },
            accessToken: sessionToken,
          );
      if (!mounted || ref.read(memberIdProvider) != id) return;
      password.clear();
      ref
          .read(chatTokenProvider.notifier)
          .setToken(result['access_token'] as String);
      setState(() => offset = 0);
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> create() async {
    if (busy) return;
    setState(() => busy = true);
    try {
      final result = await ref
          .read(memberApiProvider)
          .request(
            '/chat/rooms',
            body: {},
            accessToken: ref.read(chatTokenProvider),
          );
      if (!mounted) return;
      ref.invalidate(chatDocumentProvider);
      await Navigator.push(
        context,
        MaterialPageRoute<void>(builder: (_) => ChatRoomPage(room: result)),
      );
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final token = ref.watch(chatTokenProvider);
    final hasSessionToken =
        ref.watch(sessionProvider)?['access_token'] is String;
    return pageContent([
      heading('함께 나누는 대화', '소속팀명을 기본 이름으로 채팅방을 만들고 회원을 초대하세요.'),
      if (token == null) ...[
        Text(
          hasSessionToken
              ? '로그인한 계정으로 현재 종목의 채팅을 연결합니다.'
              : '채팅을 이용하려면 현재 종목 계정의 비밀번호로 인증해 주세요.',
        ),
        const SizedBox(height: 16),
        if (!hasSessionToken)
          TextField(
            controller: password,
            obscureText: true,
            enableSuggestions: false,
            autocorrect: false,
            decoration: const InputDecoration(labelText: '비밀번호'),
            onSubmitted: (_) => login(),
          ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: busy ? null : login,
          child: Text(busy ? '인증 중…' : '채팅 로그인'),
        ),
      ] else ...[
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: busy ? null : create,
                icon: const Icon(Icons.add_comment_outlined),
                label: const Text('채팅방 만들기'),
              ),
            ),
            IconButton(
              tooltip: '새로고침',
              onPressed: () => ref.invalidate(chatDocumentProvider),
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        ref
            .watch(chatDocumentProvider(roomsPath))
            .when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Column(
                children: [
                  Text('$e'),
                  TextButton(
                    onPressed: () {
                      if (e is ApiException && e.statusCode == 401) {
                        ref.read(chatTokenProvider.notifier).setToken(null);
                      } else {
                        ref.invalidate(chatDocumentProvider(roomsPath));
                      }
                    },
                    child: Text(
                      e is ApiException && e.statusCode == 401
                          ? '다시 로그인'
                          : '다시 시도',
                    ),
                  ),
                ],
              ),
              data: (data) => Column(
                children: [
                  if (apiRows(data).isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(24),
                      child: Text('참여 중인 채팅방이 없습니다.'),
                    ),
                  for (final room in apiRows(data))
                    Card(
                      child: ListTile(
                        leading: const Icon(Icons.forum_outlined),
                        title: Text('${room['me_name']}'),
                        subtitle: Text(
                          room['owner_id'] == ref.watch(memberIdProvider)
                              ? '내가 만든 방'
                              : '참여 중',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () async {
                          await Navigator.push(
                            context,
                            MaterialPageRoute<void>(
                              builder: (_) => ChatRoomPage(room: room),
                            ),
                          );
                          if (mounted) ref.invalidate(chatDocumentProvider);
                        },
                      ),
                    ),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      TextButton(
                        onPressed: offset == 0
                            ? null
                            : () => setState(() => offset -= 20),
                        child: const Text('이전'),
                      ),
                      Text('${offset ~/ 20 + 1} 페이지'),
                      TextButton(
                        onPressed: apiRows(data).length < 20
                            ? null
                            : () => setState(() => offset += 20),
                        child: const Text('다음'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
      ],
    ]);
  }
}
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (서비스 JWT 기반 채팅 연결)
