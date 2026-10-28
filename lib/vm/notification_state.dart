// 작업자 : 최현준
// 최초 작업 일 : 2026-10-28
import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../service/notification_service.dart';
import 'member_state.dart';

final notificationServiceProvider = Provider((ref) => NotificationService());
final notificationProvider =
    NotifierProvider<NotificationState, Map<String, dynamic>>(
      NotificationState.new,
    );

const notificationTitles = {
  'message': '새 메시지가 도착했습니다.',
  'match_confirmed': '예약한 경기의 매치가 성사되었습니다.',
  'before10': '경기 시작 10분 전입니다.',
  'absence10': '경기 시작 10분 후입니다. 출석을 확인해 주세요.',
};

/// 계정·기기 토큰 변경을 직렬 처리하여 늦은 등록이 새 회원을 덮어쓰지 않습니다.
/* **********************
 * 버그 발생 일 : 2026-10-28
 * 버그 발생 위치 : 초기 세션 등록과 로그인 리스너
 * 1. 버그 발생 위치 : build의 초기 비동기 등록
 * 2. 버그 내용 : 첫 로그인 시 같은 기기를 두 번 등록
 * 3. 디버깅 내용 : 초기 세션을 캡처하여 로그인 변경보다 먼저 큐에 등록
 * 4. 테스트 사항 : MockClient 등록 요청 1회 및 토큰 갱신·로그아웃 검사
 * 5. 결과 및 추후 보완 사항 : 회귀 테스트 통과, 실제 Android 검증 필요
 ************************/
class NotificationState extends Notifier<Map<String, dynamic>> {
  Future<void> _queue = Future.value();
  Map<String, dynamic>? _registered;
  String? _deviceToken;
  RemoteMessage? _pending;
  final _seen = <String>{};
  bool _disposed = false;

  @override
  Map<String, dynamic> build() {
    final service = ref.read(notificationServiceProvider);
    final subscriptions = <StreamSubscription>[
      service.refreshes.listen(
        (token) =>
            _enqueue(() => _bind(ref.read(sessionProvider), refreshed: token)),
      ),
      service.foreground.listen((message) => _receive(message, false)),
      service.opened.listen((message) => _receive(message, true)),
    ];
    ref.listen(sessionProvider, (_, next) {
      _enqueue(() => _bind(next));
    });
    ref.onDispose(() {
      _disposed = true;
      for (final subscription in subscriptions) {
        unawaited(subscription.cancel());
      }
    });
    // 초기 세션을 먼저 큐에 넣어 로그인 직후 초기화와 리스너가 중복 등록하지 않게 합니다.
    final initialSession = ref.read(sessionProvider);
    final initialBinding = _enqueue(() => _bind(initialSession));
    unawaited(
      Future.microtask(() async {
        if (_disposed) return;
        await initialBinding;
        try {
          final message = await service.initialMessage();
          if (!_disposed && message != null) _receive(message, true);
        } catch (_) {
          _update({'status': '알림 열기 정보를 확인하지 못했습니다. 다시 연결해 주세요.'});
        }
      }),
    );
    return {
      'status': service.supported
          ? '로그인 후 알림을 연결합니다.'
          : '푸시 알림은 Android 앱에서 지원합니다.',
    };
  }

  Future<void> _enqueue(Future<void> Function() task) {
    _queue = _queue.then((_) async {
      if (_disposed) return;
      try {
        await task();
      } catch (_) {
        _update({'status': '알림 연결에 실패했습니다. 다시 시도하거나 재로그인해 주세요.'});
      }
    });
    return _queue;
  }

  void _update(Map<String, dynamic> value) {
    if (!_disposed) state = {...state, ...value};
  }

  Future<void> retry() => _enqueue(() => _bind(ref.read(sessionProvider)));

  Future<void> _bind(Map<String, dynamic>? session, {String? refreshed}) async {
    final api = ref.read(memberApiProvider);
    final service = ref.read(notificationServiceProvider);
    if (!service.supported) return;
    if (_registered != null && _registered!['c_id'] != session?['c_id']) {
      try {
        await api.request(
          '/notifications/devices/deactivate',
          body: {'f_token': _deviceToken},
          accessToken: _registered!['access_token'] as String,
        );
      } finally {
        // 서버 연결이 끊겨도 이전 계정의 기기 주소를 더는 사용하지 않습니다.
        await service.deleteToken();
        _registered = null;
        _deviceToken = null;
        _seen.clear();
        _update({'message': null});
      }
    }
    if (session == null || _disposed) return;
    // 알림 화면 이동은 기기 재등록의 성공 여부와 독립적으로 처리합니다.
    if (_pending != null) {
      final message = _pending!;
      _pending = null;
      _receive(message, true);
    }
    final jwt = session['access_token'];
    if (jwt is! String || jwt.isEmpty) {
      _update({'status': '알림 인증을 위해 다시 로그인해 주세요.'});
      return;
    }
    final token = refreshed ?? await service.requestToken();
    if (token == null || token.isEmpty) {
      _update({'status': '알림 권한이 없거나 기기 토큰을 발급받지 못했습니다.'});
      return;
    }
    // 응답 유실로 서버 저장 여부가 불명확해도 로그아웃 시 해제할 수 있도록 시도 정보를 보관합니다.
    _registered = session;
    _deviceToken = token;
    await api.request(
      '/notifications/devices',
      body: {
        'f_token': token,
        'f_platform': 'android',
        'c_id_seq': session['c_id_seq'],
      },
      accessToken: jwt,
    );
    _update({'status': '가입한 모든 종목의 알림이 연결되었습니다.'});
  }

  void _receive(RemoteMessage message, bool open) {
    final session = ref.read(sessionProvider);
    if (session == null) {
      if (open) _pending = message;
      return;
    }
    final data = message.data;
    final members = session['member_ids'] as List? ?? [session['c_id_seq']];
    if (!members.contains(data['c_id_seq']) ||
        !notificationTitles.containsKey(data['type'])) {
      return;
    }
    final key = '${data['event_id'] ?? message.messageId}:$open';
    if (!_seen.add(key)) return;
    if (_seen.length > 200) _seen.remove(_seen.first);
    _update({'message': data, 'open': open});
  }

  void clearMessage() => _update({'message': null});
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
