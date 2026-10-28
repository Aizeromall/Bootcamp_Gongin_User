// 2026-10-28
// 작업자 : 양태건
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'member_state.dart';
import 'member_features.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 게시판 탐색 종목은 예약·결제 회원 종목과 분리합니다.
class BoardFilter {
  const BoardFilter({
    required this.sport,
    this.category = '전체',
    this.keyword = '',
    this.offset = 0,
  });
  final int sport;
  final String category;
  final String keyword;
  final int offset;
  ApiQuery get query => apiQuery('/board/select', {
    'event_category': sports[sport]!,
    if (category != '전체') 'board_category': category,
    'keyword': keyword,
    'limit': '20',
    'offset': '$offset',
  });
}

class BoardFilters extends Notifier<BoardFilter> {
  BoardFilters(this.initialCategory);
  final String initialCategory;
  @override
  BoardFilter build() {
    ref.watch(sessionProvider);
    return BoardFilter(
      sport: ref.watch(sportProvider),
      category: initialCategory,
    );
  }

  void selectSport(int value) => state = BoardFilter(
    sport: value,
    category: state.category,
    keyword: state.keyword,
  );
  void selectCategory(String value) => state = BoardFilter(
    sport: state.sport,
    category: value,
    keyword: state.keyword,
  );
  void search(String value) => state = BoardFilter(
    sport: state.sport,
    category: state.category,
    keyword: value.trim(),
  );
  void page(int offset) => state = BoardFilter(
    sport: state.sport,
    category: state.category,
    keyword: state.keyword,
    offset: offset,
  );
}

final boardFiltersProvider = NotifierProvider.autoDispose
    .family<BoardFilters, BoardFilter, String>(BoardFilters.new);

int? boardReservationId(Map<String, dynamic> post) =>
    post['board_category'] == '매칭신청'
    ? int.tryParse(
        RegExp(r'^\[예약번호:(\d+)\]')
                .firstMatch('${post['board_content'] ?? ''}')
                ?.group(1) ??
            '',
      )
    : null;

// 현재 회원이 해당 종목으로 가입한 경우에만 팀 매칭 회원 FK를 구성합니다.
String? boardMemberId(Map<String, dynamic>? session, String sportName) {
  if (session == null) return null;
  final codes = (session['preferred_stocks'] as List? ?? [])
      .map((value) => int.tryParse('$value'))
      .toSet();
  for (final entry in sports.entries) {
    if (entry.value == sportName && codes.contains(entry.key)) {
      return '${session['c_id']}_${entry.key.toString().padLeft(2, '0')}';
    }
  }
  return null;
}

final boardMatchInfoProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>?, int>((ref, seq) async {
      final session = ref.watch(sessionProvider);
      final post = await ref.watch(
        apiDocumentProvider(apiQuery('/board/select/$seq')).future,
      );
      if (!ref.mounted) return null;
      final reservationId = boardReservationId(post);
      if (reservationId == null) return null;
      final reservation = await ref.watch(
        apiDocumentProvider(apiQuery('/match/reservation/$reservationId'))
            .future,
      );
      if (!ref.mounted) return null;
      final id = boardMemberId(session, '${post['event_category']}');
      Map<String, dynamic>? data;
      Map<String, dynamic>? match;
      final own = id != null && id == post['c_id_seq'];
      if (id != null) {
        final response = await ref.watch(
          apiDocumentProvider(
            apiQuery(own ? '/team_match/requests/$seq' : '/team_match/posts', {
              'c_id_seq': id,
            }),
          ).future,
        );
        data = response;
        if (own) {
          match = Map<String, dynamic>.from(response['post'] as Map);
        } else {
          for (final row in apiRows(response)) {
            if (row['bulletin_seq'] == seq) match = row;
          }
        }
      }
      return {
        'reservation': reservation,
        'match': match,
        'member_id': id,
        'own': own,
        'can_request': !own && data?['can_request'] == true && match != null,
        'requests': own ? apiRows(data!) : <Map<String, dynamic>>[],
      };
    }, retry: (_, _) => null);

// 댓글·매칭 변경 시 조회 수가 증가하는 게시글 상세를 다시 호출하지 않습니다.
void refreshBoardThread(WidgetRef ref, int seq) {
  ref.invalidate(apiDocumentProvider(apiQuery('/board/comment/select/$seq')));
  final post = ref
      .read(apiDocumentProvider(apiQuery('/board/select/$seq')))
      .asData
      ?.value;
  final reservationId = post == null ? null : boardReservationId(post);
  if (reservationId != null) {
    ref.invalidate(
      apiDocumentProvider(apiQuery('/match/reservation/$reservationId')),
    );
  }
  final id = post == null
      ? null
      : boardMemberId(ref.read(sessionProvider), '${post['event_category']}');
  if (id != null) {
    ref.invalidate(
      apiDocumentProvider(apiQuery('/team_match/posts', {'c_id_seq': id})),
    );
    ref.invalidate(
      apiDocumentProvider(
        apiQuery('/team_match/requests/$seq', {'c_id_seq': id}),
      ),
    );
  }
  ref.invalidate(boardMatchInfoProvider(seq));
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
