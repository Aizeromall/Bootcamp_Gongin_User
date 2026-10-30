// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../service/member_api.dart';
import 'member_state.dart';

// 활성 배너는 서버가 날짜와 게시 여부를 함께 검사한 결과만 사용합니다.
final bannerProvider = FutureProvider.autoDispose<List<int>>((ref) async {
  final response = await ref.watch(memberApiProvider).request('/banner');
  final rows = response['results'];
  if (rows is! List ||
      rows.any(
        (row) =>
            row is! Map ||
            row['c_image_seq'] is! int ||
            row['c_image_seq'] <= 0,
      )) {
    throw const ApiException(502, '배너 정보를 확인할 수 없습니다.');
  }
  return [for (final row in rows) (row as Map)['c_image_seq'] as int];
}, retry: (_, _) => null);

// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
