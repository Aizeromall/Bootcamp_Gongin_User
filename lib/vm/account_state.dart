// 작업자 : 최현준 / 최초 작업 일 : 2026-10-29
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../service/member_api.dart';
import 'member_state.dart';

// 계정별 인증·조회 생명주기는 세션을 구독해 분리하고 화면 종료 시 조회 캐시는 폐기합니다.
// 수정 일 : 2026-10-30 / 작업자 : 신현진
// 상태관리 방식 변경: FutureProvider → AsyncNotifier (조회 로직·autoDispose·retry는 그대로)
class AccountProfileNotifier extends AsyncNotifier<Map<String, dynamic>> {
  @override
  Future<Map<String, dynamic>> build() async {
    final session = ref.watch(sessionProvider);
    final token = session?['access_token'];
    if (token is! String || token.isEmpty) {
      throw const ApiException(401, '다시 로그인해 주세요.');
    }
    final result = await ref
        .watch(memberApiProvider)
        .request('/auth/account', accessToken: token);
    final members = result['members'];
    if (members is! List ||
        members.isEmpty ||
        members.any((row) => row is! Map)) {
      throw const ApiException(502, '회원정보 응답을 확인할 수 없습니다.');
    }
    return result;
  }
}

final accountProfileProvider =
    AsyncNotifierProvider.autoDispose<
      AccountProfileNotifier,
      Map<String, dynamic>
    >(AccountProfileNotifier.new, retry: (_, _) => null);

// 수정 일 : 2026-10-31 / 작업자 : 신현진
// 상태관리 방식 변경: Notifier<bool> → AsyncNotifier<void>
// 처리 중 여부는 state.isLoading (화면은 ref.watch(accountActionsProvider).isLoading)
final accountActionsProvider = AsyncNotifierProvider<AccountActions, void>(
  AccountActions.new,
);

// 삭제 신청 후 다시 로그인할 때는 복구 토큰만 사용하며 일반 세션을 먼저 만들지 않습니다.
final accountRecoveryProvider =
    Provider<Future<Map<String, dynamic>> Function(String, List<int>)>((ref) {
      final api = ref.watch(memberApiProvider);
      return (recoveryToken, sports) async {
        final result = await api.request(
          '/auth/account/recovery/restore',
          accessToken: recoveryToken,
          body: {'sports': sports},
        );
        final session = result['session'];
        if (result['result'] != 'OK' ||
            session is! Map ||
            session['access_token'] is! String ||
            session['recovery_required'] == true) {
          throw const ApiException(502, '복구 결과를 확인할 수 없습니다. 다시 로그인해 주세요.');
        }
        return Map<String, dynamic>.from(session);
      };
    });

// 저장·삭제 신청을 직렬화합니다. 위젯에서 HTTP나 세션 변경을 복제하지 않습니다.
// 수정 일 : 2026-10-31 / 작업자 : 신현진
// AsyncNotifier<void> : 요청 중 AsyncLoading → 성공 AsyncData / 실패 AsyncError (예외는 화면으로 다시 전달)
class AccountActions extends AsyncNotifier<void> {
  @override
  void build() {}

  Future<void> save(Map<String, dynamic> changes) =>
      _submit('/auth/account/profile', changes);
  Future<void> withdraw() => _submit('/auth/account/withdraw', null);

  Future<void> _submit(String path, Map<String, dynamic>? changes) async {
    if (state.isLoading) throw const ApiException(409, '요청을 처리 중입니다.');
    final before = ref.read(sessionProvider);
    final token = before?['access_token'];
    if (token is! String || token.isEmpty) {
      throw const ApiException(401, '다시 로그인해 주세요.');
    }
    state = const AsyncLoading();
    try {
      final result = await ref
          .read(memberApiProvider)
          .request(
            path,
            method: changes == null ? 'POST' : 'PATCH',
            body: changes,
            accessToken: token,
          );
      if (!ref.mounted || !identical(ref.read(sessionProvider), before)) {
        throw const ApiException(409, '로그인 계정이 변경되었습니다.');
      }
      final next = result['session'];
      if (result['result'] != 'OK' || next is! Map) {
        throw const ApiException(502, '처리 결과를 확인할 수 없습니다. 다시 조회해 주세요.');
      }
      if (changes == null || next['recovery_required'] == true) {
        if (next['recovery_required'] != true ||
            next['recovery_token'] is! String ||
            (changes != null &&
                (changes['preferred_stocks'] is! List ||
                    (changes['preferred_stocks'] as List).isNotEmpty))) {
          throw const ApiException(502, '삭제 신청 결과를 확인할 수 없습니다. 다시 조회해 주세요.');
        }
        // 서버 저장 확인 후에만 로그아웃합니다. 복구 토큰은 일반 로그인 세션으로 저장하지 않습니다.
        ref.read(sessionProvider.notifier).signOut();
      } else {
        final stocks = next['preferred_stocks'];
        if (next['c_id'] != before?['c_id'] ||
            next['access_token'] is! String ||
            stocks is! List ||
            stocks.isEmpty ||
            next['recovery_required'] == true) {
          throw const ApiException(502, '변경된 회원 인증 정보를 확인할 수 없습니다.');
        }
        ref
            .read(sessionProvider.notifier)
            .signIn(Map<String, dynamic>.from(next));
        final choices = stocks
            .map((s) => int.tryParse('$s'))
            .whereType<int>()
            .where(sports.containsKey)
            .toList();
        if (choices.isNotEmpty && !choices.contains(ref.read(sportProvider))) {
          ref.read(sportProvider.notifier).select(choices.first);
        }
      }
      ref.invalidate(accountProfileProvider);
      if (ref.mounted) state = const AsyncData(null);
    } catch (error, stackTrace) {
      if (ref.mounted) state = AsyncError(error, stackTrace);
      rethrow;
    }
  }
}
// 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 신현진 (조회 provider AsyncNotifier 변환)
// 최종 수정 일 : 2026-10-31 / 작업자 : 신현진 (동작 Notifier AsyncNotifier<void> 변환)
