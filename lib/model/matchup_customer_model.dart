// ###  2026.10.22 회원 모델 클래스 구성   - 신현진

class Customer {
  final String c_id_seq;                 // 회원ID + seq
  final String c_prefer_stock;           // 선호종목
  final String c_pw;                     // Password
  final String c_name;                   // 이름
  final String c_address;                // 주소
  final String c_phone;                  // 전화번호
  final String c_gender;                 // 성별
  final DateTime c_birthday;             // 생년월일
  final String c_team;                   // 소속팀명
  final int c_rating;                    // 점수
  final String c_position;               // 선호포지션
  final String c_category;               // 종목
  final DateTime c_signupdate;           // 가입일
  final DateTime? c_deletedate;          // 탈퇴일
  final String c_login_type;             // 로그인 타입

  Customer(
    {
      required this.c_id_seq,
      required this.c_prefer_stock,
      required this.c_pw,
      required this.c_name,
      required this.c_address,
      required this.c_phone,
      required this.c_gender,
      required this.c_birthday,
      required this.c_team,
      required this.c_rating,
      required this.c_position,
      required this.c_category,
      required this.c_signupdate,
      this.c_deletedate,
      required this.c_login_type,
    }
  );

  // c_id_seq(예: admin_01)를 마지막 '_' 기준으로 아이디 / 종목 번호로 나눔
  // split('_')은 아이디에 '_'가 있으면(예: hong_gd_01) 여러 조각으로 나뉘어서 lastIndexOf 사용
  // '_'가 없는 값이면 lastIndexOf가 -1이라 substring 에러가 나므로 아이디는 전체, 번호는 빈 문자열로 처리
  String get c_id {
    final index = c_id_seq.lastIndexOf('_');
    return index == -1 ? c_id_seq : c_id_seq.substring(0, index);     // admin
  }

  String get c_seq {
    final index = c_id_seq.lastIndexOf('_');
    return index == -1 ? '' : c_id_seq.substring(index + 1);          // 01 (종목 번호: 01 축구 ~ 04 배구)
  }

  // 서버에서 받은 JSON -> Customer객체
  factory Customer.fromJson(Map<String, dynamic> json) {
    return Customer(
      c_id_seq: json['c_id_seq'] ?? "__",
      c_prefer_stock: json['c_prefer_stock'] ?? "__",
      c_pw: json['c_pw'] ?? "__",
      c_name: json['c_name'] ?? "__",
      c_address: json['c_address'] ?? "__",
      c_phone: json['c_phone'] ?? "__",
      c_gender: json['c_gender'] ?? "__",
      c_birthday: DateTime.parse(json['c_birthday']),
      c_team: json['c_team'] ?? "__",
      c_rating: json['c_rating'] ?? 0,
      c_position: json['c_position'] ?? "__",
      c_category: json['c_category'] ?? "__",
      c_signupdate: DateTime.parse(json['c_signupdate']),
      c_deletedate: DateTime.tryParse(json['c_deletedate'] ?? ''),
      c_login_type: json['c_login_type'] ?? "__",
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'c_id_seq': c_id_seq,
      'c_prefer_stock': c_prefer_stock,
      'c_pw': c_pw,
      'c_name': c_name,
      'c_address': c_address,
      'c_phone': c_phone,
      'c_gender': c_gender,
      'c_birthday': c_birthday.toIso8601String(),
      'c_team': c_team,
      'c_rating': c_rating,
      'c_position': c_position,
      'c_category': c_category,
      'c_signupdate': c_signupdate.toIso8601String(),
      'c_deletedate': c_deletedate?.toIso8601String(),
      'c_login_type': c_login_type,
    };
  }
}
