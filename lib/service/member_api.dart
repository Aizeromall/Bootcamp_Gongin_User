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
    String? accessToken,
  }) async {
    final uri = Uri.parse('$baseUrl$path').replace(queryParameters: query);
    // 수정 일 : 2026-10-27 / 작업자 : 양태건
    // 채팅 인증과 게시글 PUT을 공통 처리하며 오류 본문이 JSON이 아니어도 복구합니다.
    final headers = {
      if (body != null) 'Content-Type': 'application/json',
      if (accessToken != null) 'Authorization': 'Bearer $accessToken',
    };
    final response = await (switch (method ?? (body == null ? 'GET' : 'POST')) {
      'GET' => client.get(uri, headers: headers),
      'DELETE' => client.delete(uri, headers: headers),
      'POST' => client.post(uri, headers: headers, body: jsonEncode(body)),
      'PUT' => client.put(uri, headers: headers, body: jsonEncode(body)),
      // 수정 일 : 2026-10-29 / 작업자 : 최현준 — 회원정보 부분 수정 API.
      'PATCH' => client.patch(uri, headers: headers, body: jsonEncode(body)),
      _ => throw ArgumentError.value(method, 'method', '지원하지 않는 요청 방식'),
    }).timeout(const Duration(seconds: 20));
    dynamic data;
    try {
      data = jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ApiException(
        response.statusCode,
        '서버 응답을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.',
      );
    }
    if (response.statusCode >= 400) {
      final detail = data is Map ? data['detail'] : null;
      final message = detail is List
          ? detail
                .map((e) {
                  if (e is! Map) return '$e';
                  final loc = e['loc'];
                  final field = loc is List && loc.isNotEmpty
                      ? '${loc.last}: '
                      : '';
                  return '$field${e['msg'] ?? '입력값을 확인해 주세요.'}';
                })
                .join('\n')
          : detail is String
          ? detail
          : '요청에 실패했습니다.';
      throw ApiException(response.statusCode, message);
    }
    if (data is! Map) {
      throw ApiException(response.statusCode, '서버 응답 형식을 확인해 주세요.');
    }
    return Map<String, dynamic>.from(data);
  }
}

// 수정 일 : 2026-10-27 / 작업자 : 양태건
class ApiException implements Exception {
  const ApiException(this.statusCode, this.message);
  final int statusCode;
  final String message;
  @override
  String toString() => '$message ($statusCode)';
}
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
