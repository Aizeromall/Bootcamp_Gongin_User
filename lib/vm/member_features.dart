// 2026-10-27
// 작업자 : 양태건
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'member_state.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 값 동등성이 있는 record를 키로 사용하여 회원·검색 조건별 조회를 분리합니다.
typedef ApiQuery = ({String path, String query});
ApiQuery apiQuery(String path, [Map<String, String> query = const {}]) => (
  path: path,
  query: Uri(queryParameters: query.isEmpty ? null : query).query,
);

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 팀 신청 변경은 팀·매칭 조회만 갱신하여 게시글 상세 조회 수를 다시 증가시키지 않습니다.
final teamDataRefreshProvider = Provider<Object>((ref) => Object());

// 수정 일 : 2026-10-30 / 작업자 : 신현진
// 상태관리 방식 변경: FutureProvider → AsyncNotifier (조회 로직·키·autoDispose·retry는 그대로)
// 화면은 기존처럼 ref.watch(apiDocumentProvider(query))로 AsyncValue를 받고,
// ref.invalidate(apiDocumentProvider(query))로 다시 조회합니다.
class ApiDocumentNotifier extends AsyncNotifier<Map<String, dynamic>> {
  ApiDocumentNotifier(this.query);
  final ApiQuery query;

  @override
  Future<Map<String, dynamic>> build() {
    if (query.path.startsWith('/team/') ||
        query.path.startsWith('/team_match/')) {
      ref.watch(teamDataRefreshProvider);
    }
    ref.watch(sessionProvider);
    ref.watch(memberIdProvider);
    return ref
        .watch(memberApiProvider)
        .request(
          query.path,
          query: query.query.isEmpty ? null : Uri.splitQueryString(query.query),
        );
  }
}

final apiDocumentProvider = AsyncNotifierProvider.autoDispose
    .family<ApiDocumentNotifier, Map<String, dynamic>, ApiQuery>(
      ApiDocumentNotifier.new,
      retry: (_, _) => null,
    );

List<Map<String, dynamic>> apiRows(Map<String, dynamic> data) =>
    (data['results'] as List? ?? [])
        .map((row) => Map<String, dynamic>.from(row as Map))
        .toList();

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 매칭 게시글의 예약 상태를 실제 조회하여 성사 후 댓글·대댓글 버튼을 막습니다.
// 수정 일 : 2026-10-30 / 작업자 : 신현진
// 상태관리 방식 변경: FutureProvider → AsyncNotifier (조회 로직·키·autoDispose는 그대로)
class BoardCommentWritableNotifier extends AsyncNotifier<bool> {
  BoardCommentWritableNotifier(this.seq);
  final int seq;

  @override
  Future<bool> build() async {
    final post = await ref.watch(
      apiDocumentProvider(apiQuery('/board/select/$seq')).future,
    );
    // 수정 일 : 2026-10-28 / 작업자 : 양태건
    // 상세 화면을 닫은 뒤 이전 요청이 완료되어도 폐기된 ref를 사용하지 않습니다.
    if (!ref.mounted) return false;
    if (post['board_category'] != '매칭신청') return true;
    final mark = RegExp(r'^\[예약번호:(\d+)\]')
        .firstMatch('${post['board_content'] ?? ''}');
    if (mark == null) return true;
    final reservation = await ref.watch(
      apiDocumentProvider(apiQuery('/match/reservation/${mark.group(1)}'))
          .future,
    );
    return reservation['r_check'] != true && reservation['r_check'] != 1;
  }
}

final boardCommentWritableProvider = AsyncNotifierProvider.autoDispose
    .family<BoardCommentWritableNotifier, bool, int>(
      BoardCommentWritableNotifier.new,
    );
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 신현진 (조회 provider AsyncNotifier 변환)
