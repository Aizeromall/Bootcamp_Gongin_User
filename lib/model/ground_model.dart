// ###  2026.10.22 구장 모델 클래스 구성   - 신현진

class Ground {
  final String g_code;            // 구장코드
  final String g_name;            // 구장명
  final String g_address;         // 주소
  final int g_num;                // 수용인원
  final int g_price;              // 이용금액
  final String g_information;     // 이용정보
  final double g_lat;             // 위도
  final double g_lng;             // 경도
  final String g_time;            // 운영시간
  final String e_code;            // 종목코드

  Ground(
    {
      required this.g_code,
      required this.g_name,
      required this.g_address,
      required this.g_num,
      required this.g_price,
      required this.g_information,
      required this.g_lat,
      required this.g_lng,
      required this.g_time,
      required this.e_code
    }
  );

  // 서버에서 받은 JSON -> Ground객체 
  factory Ground.fromJson(Map<String, dynamic> json) {
    return Ground(
      // 서버(DB)는 g_code를 int로 보내므로 String으로 변환 (그대로 넣으면 타입 에러)
      g_code: json['g_code']?.toString() ?? "__",
      g_name: json['g_name'] ?? "__",
      g_address: json['g_address'] ?? "__",
      g_num: json['g_num'] ?? 0,
      g_price: json['g_price'] ?? 0,
      g_information: json['g_information'] ?? "__",
      g_lat: (json['g_lat'] as num?)?.toDouble() ?? 0.0,
      g_lng: (json['g_lng'] as num?)?.toDouble() ?? 0.0,
      g_time: json['g_time'] ?? "__",
      e_code: json['e_code'] ?? "__",
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'g_code': g_code,
      'g_name': g_name,
      'g_address': g_address,
      'g_num': g_num,
      'g_price': g_price,
      'g_information': g_information,
      'g_lat': g_lat,
      'g_lng': g_lng,
      'g_time': g_time,
      'e_code': e_code,
    };
  }
}
