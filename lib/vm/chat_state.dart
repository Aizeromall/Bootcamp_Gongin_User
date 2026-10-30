// 2026-10-27
// 작업자 : 양태건
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_refresh_state.dart';
import 'member_state.dart';
import '../service/chat_connection.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 종목별 회원 전환·로그아웃 시 토큰을 폐기하며 비밀번호는 저장하지 않습니다.
class ChatToken extends Notifier<String?> {
  @override
  String? build() {
    ref.watch(sessionProvider);
    ref.watch(memberIdProvider);
    return null;
  }

  void setToken(String? token) => state = token;
}

final chatTokenProvider = NotifierProvider<ChatToken, String?>(ChatToken.new);
final chatDocumentProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, String>((ref, path) async {
      final token = ref.watch(chatTokenProvider);
      if (token == null) throw Exception('채팅 로그인이 필요합니다.');
      final uri = Uri.parse(path);
      return ref
          .watch(memberApiProvider)
          .request(
            uri.path,
            query: uri.queryParameters.isEmpty ? null : uri.queryParameters,
            accessToken: token,
          );
    }, retry: (_, _) => null);
final chatConnectionProvider = Provider.autoDispose.family<ChatConnection, int>(
  (ref, roomId) {
    final token = ref.watch(chatTokenProvider);
    final id = ref.watch(memberIdProvider);
    // 수정 일 : 2026-10-30 / 작업자 : 김병재
    // 연결 중 토큰이 만료되면 채팅 토큰을 재발급합니다. chatTokenProvider가 바뀌면
    // 이 provider가 다시 만들어져 새 토큰으로 자동 재연결됩니다.
    final connection = ChatConnection(
      ref.watch(memberApiProvider),
      roomId,
      token ?? '',
      id,
      onExpired: () {
        if (token != null) {
          unawaited(
            ref.read(authRefreshProvider).renew(token).catchError((_) => null),
          );
        }
      },
    );
    ref.onDispose(connection.dispose);
    return connection;
  },
);
final chatMessagesProvider = StreamProvider.autoDispose
    .family<ChatSnapshot, int>((ref, roomId) {
      if (ref.watch(chatTokenProvider) == null) {
        return Stream.value(const ChatSnapshot(notice: '채팅 인증이 필요합니다.'));
      }
      final connection = ref.watch(chatConnectionProvider(roomId));
      connection.connect();
      return connection.changes.stream;
    });

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 내 ID 기준 전체 채팅방: 가입한 모든 종목 회원 ID로 각각 방 목록을 조회해 하나로 합칩니다(종목·1:1 구분 없음).
// 각 방에는 그 방에 참여한 내 종목 ID(member_id)를 붙여, 입장할 때 그 ID로 채팅을 연결합니다.
// 같은 방에 내 종목 ID가 여럿 참여했다면 한 번만 표시하며, 최근 개설 방(me_id 큰 순)부터 보여줍니다.
final chatAllRoomsProvider =
    FutureProvider.autoDispose<List<Map<String, dynamic>>>((ref) async {
      ref.watch(sessionProvider);
      final ids = ref.watch(memberIdsProvider);
      final api = ref.watch(memberApiProvider);
      final refresh = ref.read(authRefreshProvider);
      final lists = await Future.wait(
        ids.map((id) async {
          final token = await refresh.chatTokenFor(id);
          if (token == null) return const <Map<String, dynamic>>[];
          final data = await api.request(
            '/chat/rooms',
            query: {'limit': '100', 'offset': '0'},
            accessToken: token,
          );
          return [
            for (final row in data['results'] as List? ?? const [])
              {...Map<String, dynamic>.from(row as Map), 'member_id': id},
          ];
        }),
      );
      final rooms = <Object?, Map<String, dynamic>>{};
      for (final list in lists) {
        for (final room in list) {
          rooms.putIfAbsent(room['me_id'], () => room);
        }
      }
      return rooms.values.toList()..sort(
        (a, b) => (b['me_id'] as num? ?? 0).compareTo(a['me_id'] as num? ?? 0),
      );
    }, retry: (_, _) => null);
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (WebSocket 인증 만료 시 자동 재발급·재연결, 전 종목 채팅방 목록)
