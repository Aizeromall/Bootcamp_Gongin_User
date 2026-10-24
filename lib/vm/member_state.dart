// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../service/member_api.dart';

final memberApiProvider = Provider<MemberApi>((ref) {
  final api = MemberApi();
  ref.onDispose(api.client.close);
  return api;
});
const sports = {1: '축구', 2: '농구', 3: '야구', 4: '배구'};

/// 서버가 돌려준 가입 종목만 선택할 수 있습니다. 로그인 정보는 메모리에만 보관합니다.
class MemberSession extends Notifier<Map<String, dynamic>?> {
  @override
  Map<String, dynamic>? build() => null;
  void signIn(Map<String, dynamic> value) => state = value;
  void signOut() => state = null;
}

final sessionProvider = NotifierProvider<MemberSession, Map<String, dynamic>?>(
  MemberSession.new,
);

class SelectedSport extends Notifier<int> {
  @override
  int build() => 1;
  void select(int value) => state = value;
}

final sportProvider = NotifierProvider<SelectedSport, int>(SelectedSport.new);
final memberIdProvider = Provider<String>((ref) {
  final session = ref.watch(sessionProvider);
  return '${session?['c_id']}_${ref.watch(sportProvider).toString().padLeft(2, '0')}';
});
// 최종 수정 일 : 2026-10-24
