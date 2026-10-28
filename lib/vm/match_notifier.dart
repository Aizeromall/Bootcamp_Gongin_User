// 최초 작업자 : 신현진 / 최초 작업 일 : 2026-10-23
// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 구장 조회는 공통 MemberApi를 통해 API_BASE_URL과 HTTP 오류 처리를 공유합니다.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../model/ground_model.dart';
import 'member_features.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 구장 화면과 같은 서비스·API_BASE_URL·캐시를 사용합니다.
final groundListProvider = FutureProvider.autoDispose<List<Ground>>((
  ref,
) async {
  final data = await ref.watch(apiDocumentProvider(apiQuery('/ground')).future);
  return apiRows(data).map(Ground.fromJson).toList();
});
final groundDetailProvider = FutureProvider.autoDispose.family<Ground, String>((
  ref,
  code,
) async {
  final data = await ref.watch(
    apiDocumentProvider(apiQuery('/ground/${Uri.encodeComponent(code)}'))
        .future,
  );
  return Ground.fromJson(data);
});
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
