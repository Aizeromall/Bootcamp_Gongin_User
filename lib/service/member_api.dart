// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'dart:convert';

import 'package:http/http.dart' as http;

/// .env의 DB 비밀정보는 앱에 포함하지 않습니다.
class MemberApi {
  MemberApi({http.Client? client}) : client = client ?? http.Client();
  final http.Client client;
  static const baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );
  Future<Map<String, dynamic>> request(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? query,
    String? method,
  }) async {
    final uri = Uri.parse('$baseUrl$path').replace(queryParameters: query);
    // 디버그: 기존 GET·POST와 사용자 예약 취소 DELETE를 지원합니다.
    // 작업자 : 양태건 / 최종 수정일 : 2026-10-26
    final response = await (switch (method ?? (body == null ? 'GET' : 'POST')) {
      'GET' => client.get(uri),
      'DELETE' => client.delete(uri),
      'POST' => client.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ),
      _ => throw ArgumentError.value(method, 'method', '지원하지 않는 요청 방식'),
    }).timeout(const Duration(seconds: 20));
    final data = jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode >= 400) {
      final detail = data is Map ? data['detail'] : null;
      final message = detail is List
          ? detail
                .map((e) => '${(e['loc'] as List).last}: ${e['msg']}')
                .join('\n')
          : detail?.toString();
      throw Exception('${message ?? '요청 실패'} (${response.statusCode})');
    }
    return Map<String, dynamic>.from(data as Map);
  }
}
// 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
