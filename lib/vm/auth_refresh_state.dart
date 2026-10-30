// 2026-10-30
// 작업자 : 김병재
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../service/member_api.dart';
import '../service/session_storage.dart';
import 'chat_state.dart';
import 'member_state.dart';

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 만료된 로그인 JWT와 채팅 토큰을 사용자 입력 없이 다시 발급합니다.
// MemberApi의 401 처리(onUnauthorized)와 채팅 화면·WebSocket 재연결에서 함께 사용합니다.
class AuthRefresh {
  AuthRefresh(this.ref);
  final Ref ref;

  // 여러 요청이 동시에 401을 받아도 갱신 요청은 한 번만 보내고 결과를 공유합니다.
  Future<String?>? _session;
  Future<String?>? _chat;

  // 방금 발급한 채팅 토큰이 다시 거절되면(권한 없음 등) 반복 재발급하지 않도록 발급 시각을 기억합니다.
  DateTime? _chatIssuedAt;
  static const _chatRetryGap = Duration(seconds: 60);

  /// 만료된 토큰이 현재 로그인 JWT인지 채팅 토큰인지 구분해 새 토큰을 돌려줍니다.
  /// 이미 다른 토큰으로 바뀌었거나 갱신할 수 없으면 null입니다.
  Future<String?> renew(String expired) {
    if (ref.read(sessionProvider)?['access_token'] == expired) {
      return _session ??= _renewSession(expired)
          .whenComplete(() => _session = null);
    }
    if (ref.read(chatTokenProvider) == expired) {
      final issuedAt = _chatIssuedAt;
      if (issuedAt != null &&
          DateTime.now().difference(issuedAt) < _chatRetryGap) {
        return Future.value(null);
      }
      return issueChat();
    }
    // 수정 일 : 2026-10-30 / 작업자 : 김병재
    // 전 종목 채팅방 목록용으로 받아 둔 다른 종목의 채팅 토큰이면 그 종목 ID로 다시 발급합니다.
    final memberId = [
      for (final entry in _chatTokens.entries)
        if (entry.value == expired) entry.key,
    ].firstOrNull;
    if (memberId != null) {
      final issuedAt = _chatTokenIssuedAt[memberId];
      if (issuedAt != null &&
          DateTime.now().difference(issuedAt) < _chatRetryGap) {
        return Future.value(null);
      }
      _chatTokens.remove(memberId);
      return chatTokenFor(memberId);
    }
    return Future.value(null);
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 현재 선택 종목이 아닌 내 종목 ID별 채팅 토큰 보관소입니다(전 종목 채팅방 목록 조회용).
  // 로그인 계정이 바뀌면(세션 객체 변경) 이전 계정의 토큰을 모두 버립니다.
  final Map<String, String> _chatTokens = {};
  final Map<String, DateTime> _chatTokenIssuedAt = {};
  Object? _chatTokensOwner;

  /// 수정 일 : 2026-10-30 / 작업자 : 김병재
  /// 내 종목 회원 ID(예: member_02)의 채팅 토큰을 돌려줍니다. 현재 선택 종목이면 기존 채팅 토큰을 사용하고,
  /// 다른 종목이면 받아 둔 토큰을 쓰거나 로그인 JWT로 새로 발급합니다.
  Future<String?> chatTokenFor(String memberId) async {
    final session = ref.read(sessionProvider);
    if (!identical(session, _chatTokensOwner)) {
      _chatTokens.clear();
      _chatTokenIssuedAt.clear();
      _chatTokensOwner = session;
    }
    if (ref.read(memberIdProvider) == memberId) {
      return ref.read(chatTokenProvider) ?? await issueChat();
    }
    final cached = _chatTokens[memberId];
    if (cached != null) return cached;
    final token = await _requestChatToken(session, memberId);
    // 발급 중 로그아웃·계정 전환이 일어났다면 저장하지 않습니다.
    if (token == null || !identical(session, ref.read(sessionProvider))) {
      return null;
    }
    _chatTokens[memberId] = token;
    _chatTokenIssuedAt[memberId] = DateTime.now();
    return token;
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 로그인 JWT로 지정한 내 종목 ID의 채팅 토큰을 발급받습니다(POST /chat/session-token).
  Future<String?> _requestChatToken(
    Map<String, dynamic>? session,
    String memberId,
  ) async {
    final jwt = session?['access_token'];
    if (jwt is! String || jwt.isEmpty) return null;
    final result = await ref
        .read(memberApiProvider)
        .request(
          '/chat/session-token',
          body: {'c_id_seq': memberId},
          accessToken: jwt,
        );
    final token = result['access_token'];
    return token is String && token.isNotEmpty ? token : null;
  }

  // 로그인 JWT 갱신: POST /auth/refresh (만료 후 30일까지 서버에서 허용)
  Future<String?> _renewSession(String expired) async {
    final session = ref.read(sessionProvider);
    try {
      final result = await ref
          .read(memberApiProvider)
          .request(
            '/auth/refresh',
            body: const {},
            accessToken: expired,
            renewOnUnauthorized: false,
          );
      final token = result['access_token'];
      // 갱신 중 로그아웃·계정 전환이 일어났다면 이전 계정의 토큰을 저장하지 않습니다.
      if (token is! String ||
          token.isEmpty ||
          result['c_id'] != session?['c_id'] ||
          !identical(session, ref.read(sessionProvider))) {
        return null;
      }
      ref.read(sessionProvider.notifier).renewToken(token);
      // 수정 일 : 2026-10-30 / 작업자 : 김병재
      // renewToken은 세션 변경 알림을 보내지 않으므로 보안 저장소도 여기서 직접 새 토큰으로 바꿉니다.
      await ref.read(sessionStorageProvider).save(token);
      return token;
    } on ApiException {
      // 30일 경과·삭제 신청 등으로 갱신이 거절되면 원래 401 오류를 화면에 그대로 보여줍니다.
      return null;
    }
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  /// 앱 재실행 시 자동 로그인: 저장된 로그인 JWT로 /auth/refresh를 호출해 로그인 응답을 다시 받습니다.
  /// 성공하면 로그인 응답(가입 종목·회원 ID·새 토큰)을, 저장된 토큰이 없거나 실패하면 null을 돌려줍니다.
  /// 서버가 거절(30일 경과·탈퇴·삭제 신청)하면 저장된 토큰을 지우고, 네트워크 오류면 다음 실행을 위해 남겨 둡니다.
  Future<Map<String, dynamic>?> restore() async {
    final storage = ref.read(sessionStorageProvider);
    final saved = await storage.read();
    if (saved == null) return null;
    try {
      final result = await ref
          .read(memberApiProvider)
          .request(
            '/auth/refresh',
            body: const {},
            accessToken: saved,
            renewOnUnauthorized: false,
          );
      if (result['access_token'] is! String ||
          result['recovery_required'] == true) {
        await storage.clear();
        return null;
      }
      return result;
    } on ApiException catch (error) {
      if (error.statusCode < 500) await storage.clear();
      return null;
    } catch (_) {
      // 서버 미실행·연결 실패·시간 초과: 로그인 화면을 보여주고 저장된 토큰은 유지합니다.
      return null;
    }
  }

  /// 채팅 토큰 발급: 로그인 JWT로 현재 종목 회원 ID의 채팅 토큰을 받습니다(비밀번호 입력 없음).
  /// 로그인 JWT가 만료되었으면 MemberApi의 401 처리에서 JWT를 먼저 갱신한 뒤 다시 요청합니다.
  Future<String?> issueChat() =>
      _chat ??= _issueChat().whenComplete(() => _chat = null);

  Future<String?> _issueChat() async {
    final session = ref.read(sessionProvider);
    final id = ref.read(memberIdProvider);
    final token = await _requestChatToken(session, id);
    // 발급 중 종목·계정이 바뀌었다면 다른 회원 ID의 토큰을 저장하지 않습니다.
    if (token == null ||
        !identical(session, ref.read(sessionProvider)) ||
        ref.read(memberIdProvider) != id) {
      return null;
    }
    _chatIssuedAt = DateTime.now();
    ref.read(chatTokenProvider.notifier).setToken(token);
    return token;
  }
}

final authRefreshProvider = Provider<AuthRefresh>(AuthRefresh.new);

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 로그인 JWT 보안 저장소입니다. 테스트에서는 provider override로 메모리 저장소를 사용할 수 있습니다.
final sessionStorageProvider = Provider<SessionStorage>(
  (ref) => SessionStorage(),
);
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
