// 2026-10-27
// 작업자 : 양태건
import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:bootcamp_project_gongin_admin_app/service/chat_connection.dart';
import 'package:bootcamp_project_gongin_admin_app/service/member_api.dart';

class FakeSocket implements WebSocketChannel {
  final incoming = StreamController<dynamic>();
  final frames = <Map<String, dynamic>>[];
  bool closed = false;
  late final FakeSink output = FakeSink(this);
  @override
  Stream<dynamic> get stream => incoming.stream;
  @override
  WebSocketSink get sink => output;
  @override
  Future<void> get ready async {}
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class FakeSink implements WebSocketSink {
  FakeSink(this.socket);
  final FakeSocket socket;
  @override
  void add(dynamic value) =>
      socket.frames.add(jsonDecode(value as String) as Map<String, dynamic>);
  @override
  Future<void> close([int? code, String? reason]) async {
    socket.closed = true;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

http.Response jsonResponse(String body, int status) =>
    http.Response.bytes(utf8.encode(body), status);
Map<String, dynamic> message(int id, String text) => {
  's_me_id': id,
  'me_id': 7,
  'c_id_seq': 'member_01',
  's_me_content': text,
};
Future<void> flush() async {
  for (var i = 0; i < 5; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  // 수정 일 : 2026-10-27 / 작업자 : 양태건
  test('WebSocket 인증·이력/실시간 중복 제거·저장 확인·과거 페이지·연결 정리', () async {
    final socket = FakeSocket();
    final recent = Completer<http.Response>();
    final queries = <Uri>[];
    final api = MemberApi(
      client: MockClient((r) async {
        queries.add(r.url);
        expect(r.headers['Authorization'], 'Bearer token');
        if (r.url.queryParameters.containsKey('before_id')) {
          return jsonResponse(
            jsonEncode({
              'results': [message(1, '과거')],
            }),
            200,
          );
        }
        return recent.future;
      }),
    );
    final connection = ChatConnection(
      api,
      7,
      'token',
      'member_01',
      open: (uri) {
        expect(uri.path, '/chat/ws/7');
        expect(uri.scheme, 'ws');
        return socket;
      },
    );
    final snapshots = <ChatSnapshot>[];
    final subscription = connection.changes.stream.listen(snapshots.add);
    addTearDown(() async {
      connection.dispose();
      await subscription.cancel();
      await socket.incoming.close();
      api.client.close();
    });
    await connection.connect();
    expect(socket.frames.single, {'type': 'auth', 'access_token': 'token'});
    socket.incoming.add(jsonEncode({'type': 'ready'}));
    await flush();
    socket.incoming.add(
      jsonEncode({'type': 'message', 'message': message(51, '실시간')}),
    );
    recent.complete(
      jsonResponse(
        jsonEncode({
          'results': [for (var i = 2; i <= 51; i++) message(i, '기록')],
        }),
        200,
      ),
    );
    await flush();
    expect(connection.snapshot.messages.length, 50);
    expect(connection.snapshot.ready, true);
    connection.send('보낼 내용');
    connection.send('중복 클릭');
    expect(socket.frames.where((f) => f['type'] == 'message').length, 1);
    expect(connection.snapshot.pending, '보낼 내용');
    socket.incoming.add(
      jsonEncode({'type': 'message', 'message': message(52, '보낼 내용')}),
    );
    await flush();
    expect(connection.snapshot.pending, isNull);
    expect(connection.snapshot.confirmedId, 52);
    await connection.loadOlder();
    expect(queries.last.queryParameters['before_id'], '2');
    expect(connection.snapshot.messages.first['s_me_id'], 1);
    expect(connection.snapshot.hasOlder, false);
    connection.dispose();
    expect(socket.closed, true);
    expect(snapshots, isNotEmpty);
  });
  test('서버 오류 응답은 미확인 입력을 저장 성공으로 처리하지 않음', () async {
    final socket = FakeSocket();
    final api = MemberApi(
      client: MockClient((r) async => jsonResponse('{"results":[]}', 200)),
    );
    final connection = ChatConnection(
      api,
      7,
      'token',
      'member_01',
      open: (_) => socket,
    );
    final sub = connection.changes.stream.listen((_) {});
    addTearDown(() async {
      connection.dispose();
      await sub.cancel();
      await socket.incoming.close();
      api.client.close();
    });
    await connection.connect();
    socket.incoming.add('{"type":"ready"}');
    await flush();
    connection.send('실패한 메시지');
    socket.incoming.add('{"type":"error","detail":"권한을 확인해 주세요."}');
    await flush();
    expect(connection.snapshot.pending, isNull);
    expect(connection.snapshot.confirmedId, isNull);
    expect(connection.snapshot.notice, '권한을 확인해 주세요.');
  });
}
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
