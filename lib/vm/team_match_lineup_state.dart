// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../service/member_api.dart';
import 'member_state.dart';

// 수정 일 : 2026-10-30 / 작업자 : 최현준
// 로그인 계정과 선택한 예약 또는 공고별로 팀원 조회를 분리합니다.
typedef LineupQuery = ({String memberId, int? rentalId, int? postId});

final teamMatchLineupProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, LineupQuery>((ref, query) async {
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
    }, retry: (_, _) => null);

// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
