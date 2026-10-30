// 최초 작업자 : 신현진 / 최초 작업 일 : 2026-10-23
// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 구장 조회는 공통 MemberApi를 통해 API_BASE_URL과 HTTP 오류 처리를 공유합니다.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../model/ground_model.dart';
import 'member_features.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 구장 화면과 같은 서비스·API_BASE_URL·캐시를 사용합니다.
// 수정 일 : 2026-10-30 / 작업자 : 신현진
// 상태관리 방식 변경: FutureProvider → AsyncNotifier (조회 로직·키·autoDispose는 그대로)
class GroundListNotifier extends AsyncNotifier<List<Ground>> {
  @override
  Future<List<Ground>> build() async {
    final data = await ref.watch(
      apiDocumentProvider(apiQuery('/ground')).future,
    );
    return apiRows(data).map(Ground.fromJson).toList();
  }
}

final groundListProvider =
    AsyncNotifierProvider.autoDispose<GroundListNotifier, List<Ground>>(
      GroundListNotifier.new,
    );

class GroundDetailNotifier extends AsyncNotifier<Ground> {
  GroundDetailNotifier(this.code);
  final String code;

  @override
  Future<Ground> build() async {
    final data = await ref.watch(
      apiDocumentProvider(apiQuery('/ground/${Uri.encodeComponent(code)}'))
          .future,
    );
    return Ground.fromJson(data);
  }
}

final groundDetailProvider = AsyncNotifierProvider.autoDispose
    .family<GroundDetailNotifier, Ground, String>(GroundDetailNotifier.new);
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 신현진 (조회 provider AsyncNotifier 변환)
