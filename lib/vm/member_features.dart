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

final apiDocumentProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, ApiQuery>((ref, query) {
      ref.watch(sessionProvider);
      ref.watch(memberIdProvider);
      return ref
          .watch(memberApiProvider)
          .request(
            query.path,
            query: query.query.isEmpty
                ? null
                : Uri.splitQueryString(query.query),
          );
    }, retry: (_, _) => null);

List<Map<String, dynamic>> apiRows(Map<String, dynamic> data) =>
    (data['results'] as List? ?? [])
        .map((row) => Map<String, dynamic>.from(row as Map))
        .toList();
// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 매칭 게시글의 예약 상태를 실제 조회하여 성사 후 댓글·대댓글 버튼을 막습니다.
final boardCommentWritableProvider = FutureProvider.autoDispose
    .family<bool, int>((ref, seq) async {
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
    });
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
