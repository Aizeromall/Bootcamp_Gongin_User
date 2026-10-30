// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../service/member_api.dart';
import 'member_state.dart';

// 수정 일 : 2026-10-30 / 작업자 : 최현준
// 로그인 계정과 선택한 예약 또는 공고별로 팀원 조회를 분리합니다.
typedef LineupQuery = ({String memberId, int? rentalId, int? postId});

// 수정 일 : 2026-10-30 / 작업자 : 신현진
// 상태관리 방식 변경: FutureProvider → AsyncNotifier (조회 로직·키·autoDispose·retry는 그대로)
class TeamMatchLineupNotifier extends AsyncNotifier<Map<String, dynamic>> {
  TeamMatchLineupNotifier(this.query);
  final LineupQuery query;

  @override
  Future<Map<String, dynamic>> build() async {
    final token = ref.watch(sessionProvider)?['access_token'];
    if (token is! String || token.isEmpty) {
      throw const ApiException(401, '다시 로그인해 주세요.');
    }
    return ref
        .watch(memberApiProvider)
        .request(
          '/team_match/lineup-options',
          query: {
            'c_id_seq': query.memberId,
            if (query.rentalId != null) 'r_seq': '${query.rentalId}',
            if (query.postId != null) 'bulletin_seq': '${query.postId}',
          },
          accessToken: token,
        );
  }
}

final teamMatchLineupProvider = AsyncNotifierProvider.autoDispose
    .family<TeamMatchLineupNotifier, Map<String, dynamic>, LineupQuery>(
      TeamMatchLineupNotifier.new,
      retry: (_, _) => null,
    );

// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 신현진 (조회 provider AsyncNotifier 변환)
