// 2026-10-27
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../../vm/chat_state.dart';
import '../../vm/auth_refresh_state.dart';
import '../../service/member_api.dart';
import '../shared/ui.dart';
import '../shared/member_style.dart';
import 'chat_room_page.dart';

class ChatPage extends ConsumerStatefulWidget {
  const ChatPage({super.key});
  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  final password = TextEditingController();
  bool busy = false;
  // 수정 일 : 2026-10-30 / 작업자 : 김병재 — 자동 채팅 연결 실패 여부(안내 문구 전환용)
  bool failed = false;
  int offset = 0;
  String get roomsPath => '/chat/rooms?limit=20&offset=$offset';
  // MemberApi는 path의 query를 별도 인자로 다루므로 방 목록은 명시적인 provider를 사용합니다.

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 로그인 JWT가 있으면 화면을 열 때 채팅 인증을 자동으로 진행합니다(별도 로그인 버튼 입력 없음).
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) autoLogin();
    });
  }

  @override
  void dispose() {
    password.dispose();
    super.dispose();
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 채팅 토큰이 없고 로그인 JWT가 있을 때만 자동 발급합니다. 비밀번호 방식은 자동 실행하지 않습니다.
  void autoLogin() {
    if (ref.read(chatTokenProvider) == null &&
        ref.read(sessionProvider)?['access_token'] is String) {
      login();
    }
  }

  Future<void> login() async {
    final sessionToken = ref.read(sessionProvider)?['access_token'] as String?;
    if (busy || (sessionToken == null && password.text.isEmpty)) return;
    final id = ref.read(memberIdProvider);
    setState(() {
      busy = true;
      failed = false;
    });
    try {
      // 수정 일 : 2026-10-30 / 작업자 : 김병재
      // 로그인 JWT 방식은 공통 갱신 로직으로 발급합니다. JWT가 만료됐으면 /auth/refresh 후 자동 재요청합니다.
      if (sessionToken != null) {
        await ref.read(authRefreshProvider).issueChat();
        if (mounted) setState(() => offset = 0);
        return;
      }
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
      if (mounted) {
        setState(() => failed = true);
        showMessage(context, error);
      }
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
      ref.invalidate(chatAllRoomsProvider);
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

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 전 종목 채팅방 목록: 방마다 종목과 내 역할(방장/참여)을 표시합니다.
  Widget allRooms() => ref
      .watch(chatAllRoomsProvider)
      .when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Column(
          children: [
            Text('$e'),
            TextButton(
              onPressed: () => ref.invalidate(chatAllRoomsProvider),
              child: const Text('다시 시도'),
            ),
          ],
        ),
        data: (rooms) => Column(
          children: [
            if (rooms.isEmpty)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Text('참여 중인 채팅방이 없습니다.'),
              ),
            for (final room in rooms)
              Container(
                decoration: const BoxDecoration(
                  border: Border(bottom: BorderSide(color: MemberStyle.line)),
                ),
                child: ListTile(
                  contentPadding: const EdgeInsets.symmetric(vertical: 10),
                  leading: const CircleAvatar(
                    backgroundColor: MemberStyle.greenSurface,
                    child: Icon(Icons.forum_outlined, color: MemberStyle.green),
                  ),
                  title: Text(
                    '${room['me_name']}',
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  subtitle: Text(
                    '${sports[sportOfMember(room['member_id'] as String?)] ?? ''} · '
                    '${room['owner_id'] == room['member_id'] ? '내가 만든 방' : '참여 중'}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => openRoom(room),
                ),
              ),
          ],
        ),
      );

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 방 입장: 그 방에 참여한 내 종목 ID로 채팅을 연결해야 하므로 선택 종목을 그 종목으로 맞춘 뒤 입장합니다.
  // 종목이 바뀌면 채팅 토큰이 비워지고, 이 화면의 자동 인증이 새 종목 ID로 다시 발급합니다.
  Future<void> openRoom(Map<String, dynamic> room) async {
    final navigator = Navigator.of(context);
    final sport = sportOfMember(room['member_id'] as String?);
    if (sport != null && room['member_id'] != ref.read(memberIdProvider)) {
      ref.read(sportProvider.notifier).select(sport);
    }
    await navigator.push(
      MaterialPageRoute<void>(builder: (_) => ChatRoomPage(room: room)),
    );
    if (mounted) ref.invalidate(chatAllRoomsProvider);
  }

  @override
  Widget build(BuildContext context) {
    final token = ref.watch(chatTokenProvider);
    final hasSessionToken =
        ref.watch(sessionProvider)?['access_token'] is String;
    // 수정 일 : 2026-10-30 / 작업자 : 김병재
    // 종목 변경·401 재시도 등으로 채팅 토큰이 비워지면 다음 프레임에 자동으로 다시 발급합니다.
    ref.listen(chatTokenProvider, (previous, next) {
      if (previous != null && next == null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) autoLogin();
        });
      }
    });
    return pageContent([
      heading('함께 나누는 대화', '소속팀명을 기본 이름으로 채팅방을 만들고 회원을 초대하세요.'),
      if (token == null) ...[
        Text(
          hasSessionToken
              // 수정 일 : 2026-10-30 / 작업자 : 김병재 — 자동 연결 중 안내, 실패 시 아래 버튼으로 재시도
              ? (failed
                    ? '채팅 연결에 실패했습니다. 다시 연결해 주세요.'
                    : '로그인한 계정으로 채팅을 연결하는 중입니다…')
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
          child: Text(
            busy
                ? '인증 중…'
                : hasSessionToken
                ? '다시 연결'
                : '채팅 로그인',
          ),
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
              onPressed: () {
                ref.invalidate(chatDocumentProvider);
                // 수정 일 : 2026-10-30 / 작업자 : 김병재 — 전 종목 채팅방 목록도 다시 조회
                ref.invalidate(chatAllRoomsProvider);
              },
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        // 수정 일 : 2026-10-30 / 작업자 : 김병재
        // 로그인 JWT가 있으면 내 모든 종목의 채팅방을 한 목록으로, 없으면(비밀번호 인증) 기존 현재 종목 목록을 보여줍니다.
        if (hasSessionToken)
          allRooms()
        else
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
                      // 수정 일 : 2026-10-28 / 작업자 : 양태건
                      // 마지막 메시지·읽음 수는 API에 없으므로 방 이름과 실제 참여 권한만 표시합니다.
                      Container(
                        decoration: const BoxDecoration(
                          border: Border(
                            bottom: BorderSide(color: MemberStyle.line),
                          ),
                        ),
                        child: ListTile(
                          contentPadding: const EdgeInsets.symmetric(
                            vertical: 10,
                            horizontal: 0,
                          ),
                          leading: const CircleAvatar(
                            backgroundColor: MemberStyle.greenSurface,
                            child: Icon(
                              Icons.forum_outlined,
                              color: MemberStyle.green,
                            ),
                          ),
                          title: Text(
                            '${room['me_name']}',
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
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
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (서비스 JWT 기반 채팅 연결)
// 수정 일 : 2026-10-29 / 작업자 : 양태건
// 병합: 서비스 JWT 채팅 연결과 회원 앱 목록 디자인의 두 작업 이력을 보존합니다.
// 최종 수정 일 : 2026-10-29 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (로그인 JWT로 채팅 자동 인증·재인증)
