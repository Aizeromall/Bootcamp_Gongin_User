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
// 수정 일 : 2026-10-29 / 작업자 : 최현준 — 가입·수정 화면에서 같은 포지션 계약 사용.
const sportPositions = {
  1: ['FW', 'MF', 'DF', 'GK'],
  2: ['센터', '가드', '포워드'],
  3: ['투수', '포수', '내야수', '외야수'],
  4: ['세터', '리베로', '센터', '레프트', '라이트'],
};

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
// 최종 수정 일 : 2026-10-26 / 작업자 : 양태건

// 디버그: 구장 탐색 종목은 회원별 예약·결제에 사용하는 종목과 분리합니다.
// 작업자 : 양태건 / 최종 수정일 : 2026-10-26
class GroundSport extends Notifier<int> {
  @override
  int build() {
    ref.watch(sessionProvider);
    return ref.read(sportProvider);
  }

  void select(int value) => state = value;
}

final groundSportProvider = NotifierProvider<GroundSport, int>(GroundSport.new);

class GroundRegion extends Notifier<String> {
  @override
  String build() {
    ref.watch(sessionProvider);
    return '전체 지역';
  }

  void select(String value) => state = value;
}

final groundRegionProvider = NotifierProvider<GroundRegion, String>(
  GroundRegion.new,
);
// 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
