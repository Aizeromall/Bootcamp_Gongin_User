// 2026-10-30
// 작업자 : 김병재
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'member_features.dart';
import 'member_state.dart';

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 팀 탭의 종목별 소속팀 상태입니다. 종목 하나(sport)마다 소속팀(team)·가입 대기 팀(pending)을 가집니다.
class SportTeam {
  const SportTeam({
    required this.memberId,
    required this.sport,
    this.team,
    this.pending = const [],
  });
  final String memberId;
  final int sport;
  final Map<String, dynamic>? team;
  final List<Map<String, dynamic>> pending;
  bool get isCaptain => team?['is_captain'] == true;
}

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// GET /my_team: 로그인 JWT의 모든 종목 소속팀을 한 번에 조회합니다.
// 가입 신청·승인·탈퇴 후 teamDataRefreshProvider 무효화로 함께 다시 조회됩니다.
// 로그인 JWT가 없는 세션(비밀번호 채팅 인증 등 이전 흐름)은 서버 조회 없이 모든 종목을 '팀 없음'으로 표시합니다.
final myTeamProvider = FutureProvider.autoDispose<List<SportTeam>>((ref) async {
  ref.watch(teamDataRefreshProvider);
  final session = ref.watch(sessionProvider);
  final ids = ref.watch(memberIdsProvider);
  final token = session?['access_token'];
  final rows = <String, Map<String, dynamic>>{};
  if (token is String && token.isNotEmpty) {
    final data = await ref
        .watch(memberApiProvider)
        .request('/my_team', accessToken: token);
    for (final row in apiRows(data)) {
      rows['${row['c_id_seq']}'] = row;
    }
  }
  // 화면 순서는 가입 종목 순서를 따르고, 서버 응답에 없는 종목도 '팀 없음'으로 보여줍니다.
  return [
    for (final id in ids)
      if (sportOfMember(id) case final sport?)
        SportTeam(
          memberId: id,
          sport: sport,
          team: rows[id]?['team'] is Map
              ? Map<String, dynamic>.from(rows[id]!['team'] as Map)
              : null,
          pending: [
            for (final p in rows[id]?['pending'] as List? ?? const [])
              Map<String, dynamic>.from(p as Map),
          ],
        ),
  ];
}, retry: (_, _) => null);

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// GET /my_team/members/{t_id}: 내 소속팀의 팀원 목록(팀장 먼저)입니다.
final teamMembersProvider = FutureProvider.autoDispose
    .family<List<Map<String, dynamic>>, int>((ref, teamId) async {
      ref.watch(teamDataRefreshProvider);
      final token = ref.watch(sessionProvider)?['access_token'];
      if (token is! String || token.isEmpty) return const [];
      final data = await ref
          .watch(memberApiProvider)
          .request('/my_team/members/$teamId', accessToken: token);
      return apiRows(data);
    }, retry: (_, _) => null);

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 팀 종목은 팀 개설자 회원 ID 끝자리로 판단합니다(team 테이블에 종목 컬럼이 없음).
int? teamSport(Map<String, dynamic> team) =>
    sportOfMember(team['creator_id'] as String?);

// 종목 아이콘(팀 탭 카드·배너 표시용)
const sportIcons = {1: '⚽', 2: '🏀', 3: '⚾', 4: '🏐'};
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
