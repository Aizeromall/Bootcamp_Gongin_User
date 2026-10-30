// 작업자 : 최현준
// 최초 작업 일 : 2026-10-30

// 실력 매칭의 예상 1인 이용료입니다. 최종 금액은 서버에서 계산합니다.
int? individualGroundPrice(Object? rawPrice, Object? rawCapacity) {
  final price = num.tryParse('$rawPrice');
  final capacity = num.tryParse('$rawCapacity');
  if (price == null ||
      capacity == null ||
      !price.isFinite ||
      !capacity.isFinite ||
      price < 0 ||
      capacity <= 0) {
    return null;
  }
  return (price / capacity).round();
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
