// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
// 수정 일 : 2026-11-02 / 작업자 : 신현진
// rental_availability_page.dart 안에 있던 _rentalOptionsProvider(FutureProvider)를 vm으로 옮기고
// AsyncNotifier로 변경했습니다. 조회 로직·조회 키·autoDispose·retry는 그대로입니다.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'member_features.dart';
import 'member_state.dart';

typedef RentalKey = ({String date, int sport});
typedef RentalOption = ({
  Map<String, dynamic> ground,
  Map<String, dynamic> slot,
});

// 날짜와 회원 종목을 조회 키로 분리해 이전 검색의 결과가 섞이지 않게 합니다.
class RentalOptionsNotifier extends AsyncNotifier<List<RentalOption>> {
  RentalOptionsNotifier(this.key);
  final RentalKey key;

  @override
  Future<List<RentalOption>> build() async {
    final grounds = apiRows(
      await ref.watch(apiDocumentProvider(apiQuery('/ground')).future),
    );
    final matching = grounds.where((ground) {
      final info = '${ground['g_information'] ?? ''}';
      final text =
          RegExp(r'(?:^|/)\s*종목\s*:\s*([^/]+)').firstMatch(info)?.group(1) ??
          '';
      return text.split(RegExp(r'[,·、\s]+')).contains(sports[key.sport]);
    });
    final options = await Future.wait(
      matching.map((ground) async {
        final response = await ref.watch(
          apiDocumentProvider(
            apiQuery('/ground/reservation/slots/${ground['g_code']}', {
              'r_date': key.date,
            }),
          ).future,
        );
        return [
          for (final raw in response['slots'] as List? ?? [])
            if (raw is Map && raw['is_available'] == true)
              (ground: ground, slot: Map<String, dynamic>.from(raw)),
        ];
      }),
    );
    return options.expand((rows) => rows).toList();
  }
}

final rentalOptionsProvider = AsyncNotifierProvider.autoDispose
    .family<RentalOptionsNotifier, List<RentalOption>, RentalKey>(
      RentalOptionsNotifier.new,
      retry: (_, _) => null,
    );

// 최종 수정 일 : 2026-11-02 / 작업자 : 신현진 (FutureProvider → AsyncNotifier 변환, vm으로 이동)
