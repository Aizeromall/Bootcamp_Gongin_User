// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../service/member_api.dart';
import 'auth_refresh_state.dart';

final memberApiProvider = Provider<MemberApi>((ref) {
  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 401 응답 시 로그인 JWT·채팅 토큰을 자동 갱신합니다. 테스트의 provider override에는 적용되지 않습니다.
  final api = MemberApi(
    onUnauthorized: (expired) => ref.read(authRefreshProvider).renew(expired),
  );
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

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 토큰 갱신: 같은 세션 객체의 access_token만 바꿉니다. 새 객체로 교체하지 않으므로
  // identical(session, ...) 계정 전환 검사와 세션을 구독하는 구장 종목·지역·채팅 선택값이 초기화되지 않습니다.
  void renewToken(String token) {
    final session = state;
    if (session != null) session['access_token'] = token;
  }
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

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 로그인 계정의 모든 가입(선호) 종목 회원 ID입니다. 종목 Dropdown과 관계없이 팀 탭·채팅 전체 조회에 사용합니다.
// 로그인 응답의 member_ids를 우선 사용하고, 없으면 preferred_stocks로 'ID_0N' 형식을 만듭니다.
final memberIdsProvider = Provider<List<String>>((ref) {
  final session = ref.watch(sessionProvider);
  if (session == null) return const [];
  final ids = session['member_ids'];
  if (ids is List && ids.isNotEmpty) return ids.whereType<String>().toList();
  final fromStocks = [
    for (final stock in session['preferred_stocks'] as List? ?? const [])
      if (int.tryParse('$stock') case final sport?
          when sports.containsKey(sport))
        '${session['c_id']}_${sport.toString().padLeft(2, '0')}',
  ];
  // 가입 종목 정보가 없는 세션(이전 형식)은 현재 선택 종목 ID 하나만 사용합니다.
  return fromStocks.isNotEmpty ? fromStocks : [ref.watch(memberIdProvider)];
});

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 종목 코드에 해당하는 내 회원 ID입니다(가입하지 않은 종목이면 null).
String? myMemberIdFor(List<String> ids, int? sport) =>
    ids.where((id) => sportOfMember(id) == sport).firstOrNull;

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 회원 ID 끝 두 자리로 종목 코드를 구합니다(member_02 → 2). 형식이 다르면 null입니다.
int? sportOfMember(String? memberId) {
  if (memberId == null || memberId.length < 3) return null;
  final sport = int.tryParse(memberId.substring(memberId.length - 2));
  return sports.containsKey(sport) ? sport : null;
}
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
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (로그인 토큰 자동 갱신 연결)
// 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
