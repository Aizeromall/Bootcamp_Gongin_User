// 2026-10-27
// 작업자 : 양태건
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
    final connection = ChatConnection(
      ref.watch(memberApiProvider),
      roomId,
      token ?? '',
      id,
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
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
