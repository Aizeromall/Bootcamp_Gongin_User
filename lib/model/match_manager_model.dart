// ###  2026.10.22 구장매니저 모델 클래스 구성   - 신현진

class MatchManager {
  final String m_id;                        // 매니저ID
  final String m_pw;                        // Password
  final String m_name;                      // 이름
  final String m_phone;                     // 전화번호
  final String m_gender;                    // 성별
  final String m_workplace;                 // 근무지
  final DateTime? m_resianationdate;        // 퇴사일

  MatchManager(
    {
      required this.m_id,
      required this.m_pw,
      required this.m_name,
      required this.m_phone,
      required this.m_gender,
      required this.m_workplace,
      this.m_resianationdate
    }
  );

  // 서버에서 받은 JSON -> MatchManager객체 
  factory MatchManager.fromJson(Map<String, dynamic> json) {
    return MatchManager(
      m_id: json['m_id'] ?? "__",
      m_pw: json['m_pw'] ?? "__",
      m_name: json['m_name'] ?? "__",
      m_phone: json['m_phone'] ?? "__",
      m_gender: json['m_gender'] ?? "__",
      m_workplace: json['m_workplace'] ?? "__",
      m_resianationdate: DateTime.tryParse(json['m_resianationdate'] ?? ''),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'm_id': m_id,
      'm_pw': m_pw,
      'm_name': m_name,
      'm_phone': m_phone,
      'm_gender': m_gender,
      'm_workplace': m_workplace,
      'm_resianationdate': m_resianationdate?.toIso8601String(),
    };
  }
}
