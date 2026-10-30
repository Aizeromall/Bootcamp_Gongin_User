// 2026-10-27
// 작업자 : 양태건
import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import 'member_api.dart';

class ChatSnapshot {
  const ChatSnapshot({
    this.messages = const [],
    this.ready = false,
    this.notice = '연결 중…',
    this.pending,
    this.hasOlder = false,
    this.confirmedId,
  });
  final List<Map<String, dynamic>> messages;
  final bool ready;
  final String notice;
  final String? pending;
  final bool hasOlder;
  final int? confirmedId;
}

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 소켓·메시지 캐시를 provider 생명주기에 묶고 저장 확인 전에는 입력을 지우지 않습니다.
class ChatConnection {
  ChatConnection(
    this.api,
    this.roomId,
    this.token,
    this.memberId, {
    this.open = WebSocketChannel.connect,
    this.onExpired,
  });
  final WebSocketChannel Function(Uri) open;
  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 서버가 인증 만료·거절(1008)로 연결을 닫으면 호출합니다. 채팅 토큰을 재발급하면
  // provider가 새 토큰으로 연결을 다시 만들고, 이력은 마지막 50개부터 다시 불러옵니다.
  final void Function()? onExpired;
  final MemberApi api;
  final int roomId;
  final String token;
  final String memberId;
  final changes = StreamController<ChatSnapshot>.broadcast();
  final Map<int, Map<String, dynamic>> _messages = {};
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  Timer? _ackTimer;
  Timer? _authTimer;
  bool _closed = false;
  bool _connected = false;
  bool _ready = false;
  bool _older = false;
  bool _loadingOlder = false;
  String? _pending;
  int? _confirmedId;
  String _notice = '연결 중…';
  ChatSnapshot get snapshot {
    final rows = _messages.values.toList()
      ..sort((a, b) => (a['s_me_id'] as int).compareTo(b['s_me_id'] as int));
    return ChatSnapshot(
      messages: rows,
      ready: _ready,
      notice: _notice,
      pending: _pending,
      hasOlder: _older,
      confirmedId: _confirmedId,
    );
  }

  void _emit() {
    if (!_closed) changes.add(snapshot);
  }

  void _merge(Map<String, dynamic> data) {
    for (final row in data['results'] as List? ?? []) {
      final value = Map<String, dynamic>.from(row as Map);
      _messages[value['s_me_id'] as int] = value;
    }
  }

  Future<void> connect() async {
    try {
      final base = Uri.parse(MemberApi.baseUrl);
      final uri = base.replace(
        scheme: base.scheme == 'https' ? 'wss' : 'ws',
        path: '${base.path}/chat/ws/$roomId',
      );
      final channel = _channel = open(uri);
      await channel.ready.timeout(const Duration(seconds: 12));
      if (_closed) {
        unawaited(channel.sink.close());
        return;
      }
      _connected = true;
      _subscription = channel.stream.listen(
        _receive,
        onError: (Object e) => _disconnected('채팅 연결에 실패했습니다.'),
        onDone: () {
          // 수정 일 : 2026-10-30 / 작업자 : 김병재
          // 1008은 서버의 토큰 만료·인증 실패 종료 코드입니다. 이때만 자동 재인증을 요청합니다.
          // 전송 중이던 입력은 저장 여부가 불명확하므로 자동 재전송하지 않습니다.
          final expired =
              !_closed && onExpired != null && channel.closeCode == 1008;
          _disconnected(
            expired ? '채팅 인증을 갱신하는 중입니다…' : '연결이 종료되었습니다. 다시 연결해 주세요.',
          );
          if (expired) onExpired?.call();
        },
      );
      channel.sink.add(jsonEncode({'type': 'auth', 'access_token': token}));
      _authTimer = Timer(const Duration(seconds: 12), () {
        _disconnected('채팅 인증 시간이 초과되었습니다.');
        unawaited(channel.sink.close());
      });
    } catch (_) {
      _disconnected('서버에 연결할 수 없습니다. 다시 연결해 주세요.');
    }
  }

  void _disconnected(String text) {
    if (_closed) return;
    _ready = false;
    _connected = false;
    _notice = text;
    _authTimer?.cancel();
    _emit();
  }

  Future<void> _receive(dynamic raw) async {
    if (_closed) return;
    try {
      final data = jsonDecode(raw as String) as Map<String, dynamic>;
      if (data['type'] == 'ready') {
        _authTimer?.cancel();
        // 먼저 실시간 수신을 시작하고 이력을 합쳐 조회 중 도착한 메시지도 보존합니다.
        final recent = await api.request(
          '/chat/rooms/$roomId/messages',
          query: {'limit': '50'},
          accessToken: token,
        );
        if (_closed || !_connected) return;
        _merge(recent);
        _older = (recent['results'] as List).length == 50;
        _ready = true;
        _notice = '실시간 연결됨';
      } else if (data['type'] == 'message') {
        final row = Map<String, dynamic>.from(data['message'] as Map);
        _messages[row['s_me_id'] as int] = row;
        if (row['c_id_seq'] == memberId && row['s_me_content'] == _pending) {
          _confirmedId = row['s_me_id'] as int;
          _pending = null;
          _ackTimer?.cancel();
        }
      } else if (data['type'] == 'error') {
        _pending = null;
        _ackTimer?.cancel();
        _notice = '${data['detail'] ?? '메시지를 전송하지 못했습니다.'}';
      }
      _emit();
    } catch (_) {
      _disconnected('메시지를 확인하지 못했습니다. 다시 연결해 주세요.');
    }
  }

  void send(String text) {
    if (!_ready || _pending != null || text.trim().isEmpty) return;
    _pending = text.trim();
    _emit();
    _channel!.sink.add(jsonEncode({'type': 'message', 'content': _pending}));
    _ackTimer = Timer(const Duration(seconds: 15), () {
      _ready = false;
      _notice = '저장 확인이 지연되고 있습니다. 다시 연결해 이력을 확인해 주세요. 입력은 자동 재전송하지 않습니다.';
      _emit();
    });
  }

  Future<void> loadOlder() async {
    if (_loadingOlder || !_older || _messages.isEmpty) return;
    _loadingOlder = true;
    try {
      final before = _messages.keys.reduce((a, b) => a < b ? a : b);
      final data = await api.request(
        '/chat/rooms/$roomId/messages',
        query: {'limit': '50', 'before_id': '$before'},
        accessToken: token,
      );
      if (_closed) return;
      _merge(data);
      _older = (data['results'] as List).length == 50;
      _emit();
    } catch (_) {
      _notice = '이전 메시지를 불러오지 못했습니다.';
      _emit();
    } finally {
      _loadingOlder = false;
    }
  }

  void dispose() {
    _closed = true;
    _authTimer?.cancel();
    _ackTimer?.cancel();
    unawaited(_subscription?.cancel());
    unawaited(_channel?.sink.close());
    unawaited(changes.close());
  }
}
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (인증 만료 종료 시 자동 재인증 요청)
