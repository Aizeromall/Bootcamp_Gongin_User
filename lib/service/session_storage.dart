// 2026-10-30
// 작업자 : 김병재
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 앱 재실행 시 자동 로그인을 위해 로그인 JWT만 기기 보안 저장소(Android Keystore·iOS Keychain)에 보관합니다.
// 비밀번호와 채팅 토큰은 저장하지 않습니다. 저장소를 쓸 수 없는 환경(테스트·미지원 플랫폼)에서는
// 오류를 내지 않고 자동 로그인만 건너뜁니다.
class SessionStorage {
  SessionStorage([FlutterSecureStorage? storage])
    : _storage = storage ?? const FlutterSecureStorage();
  final FlutterSecureStorage _storage;
  static const _key = 'gongin_login_token';

  Future<String?> read() async {
    try {
      final token = await _storage.read(key: _key);
      return token == null || token.isEmpty ? null : token;
    } catch (_) {
      return null;
    }
  }

  Future<void> save(String token) async {
    try {
      await _storage.write(key: _key, value: token);
    } catch (_) {
      // 저장 실패 시 현재 실행 중인 로그인은 유지되며, 다음 실행에서 다시 로그인하면 됩니다.
    }
  }

  Future<void> clear() async {
    try {
      await _storage.delete(key: _key);
    } catch (_) {}
  }
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
