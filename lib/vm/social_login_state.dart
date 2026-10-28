// 작업자 : 최현준
// 최초 작업 일 : 2026-10-28
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../service/social_login_service.dart';
import 'member_state.dart';

final socialLoginServiceProvider = Provider((ref) => SocialLoginService());
// 화면을 벗어나도 로그아웃 시 공급자 로컬 인증 상태를 정리합니다.
final socialLogoutProvider = Provider<void>((ref) {
  final service = ref.watch(socialLoginServiceProvider);
  ref.listen(sessionProvider, (previous, next) {
    if (previous != null && previous['c_id'] != next?['c_id']) {
      // 앱 세션은 이미 종료했으며 공급자 정리 실패 원문(토큰 포함 가능)은 출력하지 않습니다.
      service
          .signOut(previous['c_login_type'] as String?)
          .catchError((Object _) {});
    }
  });
});
final socialLoginProvider =
    Provider<Future<Map<String, dynamic>> Function(String)>((ref) {
      final service = ref.watch(socialLoginServiceProvider);
      final api = ref.watch(memberApiProvider);
      return (provider) async {
        final token = await service.authenticate(provider);
        return api.request(
          provider == 'google'
              ? '/auth/google/login'
              : '/auth/$provider/mobile',
          body: {provider == 'google' ? 'id_token' : 'access_token': token},
        );
      };
    });

/// 일반·간편 로그인 모두 서버가 돌려준 가입 종목만 사용합니다.
void acceptMemberSession(WidgetRef ref, Map<String, dynamic> result) {
  final available = (result['preferred_stocks'] as List? ?? [])
      .map((value) => int.tryParse('$value'))
      .whereType<int>()
      .where(sports.containsKey)
      .toList();
  if (available.isEmpty) throw Exception('가입 종목 정보를 확인할 수 없습니다.');
  ref.read(sportProvider.notifier).select(available.first);
  ref.read(sessionProvider.notifier).signIn(result);
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
