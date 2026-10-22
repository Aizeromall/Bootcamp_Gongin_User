// ###  2026.10.22 본사직원 모델 클래스 구성   - 신현진

class Headquarter {
  final String h_id;                    // 직원ID
  final String h_position;              // 직급
  final String h_pw;                    // Password
  final String h_department;            // 부서
  final String h_name;                  // 이름
  final String h_phone;                 // 전화번호
  final DateTime? h_resignationdate;    // 퇴사일
  final DateTime h_startdate;           // 입사일

  Headquarter(
    {
      required this.h_id,
      required this.h_position,
      required this.h_pw,
      required this.h_department,
      required this.h_name,
      required this.h_phone,
      this.h_resignationdate,           // nullable이라 안 넘기면 null
      required this.h_startdate
    }
  );

  // 서버에서 받은 JSON -> Headquarter객체 
  factory Headquarter.fromJson(Map<String, dynamic> json) {
    return Headquarter(
      h_id: json['h_id'] ?? "__",
      h_position: json['h_position'] ?? "__",
      h_pw: json['h_pw'] ?? "__",
      h_department: json['h_department'] ?? "__",
      h_name: json['h_name'] ?? "__",
      h_phone: json['h_phone'] ?? "__",
      h_resignationdate: DateTime.tryParse(json['h_resignationdate'] ?? ''),
      h_startdate: DateTime.parse(json['h_startdate']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'h_id': h_id,
      'h_position': h_position,
      'h_pw': h_pw,
      'h_department': h_department,
      'h_name': h_name,
      'h_phone': h_phone,
      'h_resignationdate': h_resignationdate?.toIso8601String(),
      'h_startdate': h_startdate.toIso8601String(),

    };
  }
}
