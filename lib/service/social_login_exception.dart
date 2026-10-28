// 작업자 : 최현준
// 최초 작업 일 : 2026-10-28
/// SDK 오류 원문(토큰 포함 가능) 대신 안전한 사용자 안내만 전달합니다.
class SocialLoginException implements Exception {
  const SocialLoginException(this.message);
  final String message;
  @override
  String toString() => message;
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
