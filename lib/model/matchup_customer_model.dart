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
  final String c_position;               // 선호포지션
  final String c_category;               // 종목
  final DateTime c_signupdate;           // 가입일
  final DateTime c_deletedate;           // 탈퇴일

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
      required this.c_position,
      required this.c_category,
      required this.c_signupdate,
      required this.c_deletedate,
    }
  );

  // 서버에서 받은 JSON -> Student객체 
  factory Customer.fromJson(Map<String, dynamic> json) {
    return Customer(
      c_id_seq: json['c_id_seq'] ?? "__",
      c_prefer_stock: json['c_prefer_stock'] ?? "__",
      c_pw: json['c_pw'] ?? "__",
      c_name: json['c_name'] ?? "__",
      c_address: json['c_address'] ?? "__",
      c_phone: json['c_phone'] ?? "__",
      c_gender: json['c_gender'] ?? "__",
      c_birthday: json['c_birthday'] ?? "__",
      c_team: json['c_team'] ?? "__",
      c_position: json['c_position'] ?? "__",
      c_category: json['c_category'] ?? "__",
      c_signupdate: json['c_signupdate'] ?? "__",
      c_deletedate: json['c_deletedate'] ?? "__"
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
      'c_birthday': c_birthday,
      'c_team': c_team,
      'c_position': c_position,
      'c_category': c_category,
      'c_signupdate': c_signupdate,
      'c_deletedate': c_deletedate,
    };
  }
}