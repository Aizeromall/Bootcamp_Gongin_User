# 작업자 : 김병재
# 최초 작업 일 : 2026-10-27

# 이의신청 접수(insert_appeal) / 내 이의신청 내역(list_appeal)이 함께 쓰는 공통 코드
#   - 이의신청 사유 종류, 이의신청 상태 이름표, a_reason 분리 함수
#
# [a_reason 형식] appeal 테이블에는 제재 번호·사유·결과 컬럼이 없고 a_evidence는 50자라서
#   a_reason 앞에 대괄호 태그를 붙여 저장 (관리자 서버 appeal/appeal_common.py와 반드시 같은 형식 사용, 태그 순서는 상관없음)
#   "[제재:12][사유:사실과 다름][증빙:링크1,링크2] 상세 내용"
#     제재 : 이의신청 대상 제재 번호 (c_sanction.cs_seq)
#     사유 : 이의신청 사유 종류 (사실과 다름 / 과도한 제재 / 신고자 오인)
#     증빙 : 증빙 공유 링크 (쉼표로 이어 저장, 최대 3개, 선택)
#     결과 : 본사 처리 결과 "인용" 또는 "기각" (회원 앱에서는 읽기만 하고, 본사가 처리할 때 붙임)
#
# [이의신청 상태] appeal 테이블에 상태 컬럼이 없어서 아래 규칙으로 판단 (관리자 서버와 같은 규칙)
#   인용 / 기각 : a_reason에 [결과:인용] 또는 [결과:기각] 태그가 있음
#   재심의 중   : h_id에 재심의를 시작한 본사 직원 ID가 있고 결과는 아직 없음
#   접수        : h_id가 NULL
import re

# 이의신청 사유 종류 (화면의 "이의 사유" 칩 3개)
APPEAL_TYPES = ("사실과 다름", "과도한 제재", "신고자 오인")

# 이의신청 상태 번호 → 이름
STATE_RECEIVED = 0   # 접수
STATE_REVIEWING = 1  # 재심의 중
STATE_ACCEPTED = 2   # 인용
STATE_REJECTED = 3   # 기각
STATE_TEXT = {
    STATE_RECEIVED: "접수",
    STATE_REVIEWING: "재심의 중",
    STATE_ACCEPTED: "인용",
    STATE_REJECTED: "기각",
}
RESULT_STATE = {"인용": STATE_ACCEPTED, "기각": STATE_REJECTED}

# 대괄호 태그 하나("[이름:값]")를 문자열 맨 앞에서 떼어 내는 패턴
TAG_PATTERN = re.compile(r"^\[([^\[\]:]+):([^\[\]]*)\]\s*")


# a_reason 앞에 붙은 "[이름:값]" 태그들을 모두 떼어 {이름: 값}과 나머지 본문으로 반환
def parse_appeal_reason(reason: str):
    tags = {}
    text = reason or ""
    while True:
        found = TAG_PATTERN.match(text)
        if not found:
            break
        tags[found.group(1).strip()] = found.group(2).strip()
        text = text[found.end():]
    return tags, text


# 이의신청 상태 번호 판단: 결과 태그가 있으면 인용/기각 > 처리자(h_id)가 있으면 재심의 중 > 접수
def get_state(h_id, tags: dict) -> int:
    if tags.get("결과") in RESULT_STATE:
        return RESULT_STATE[tags["결과"]]
    if h_id is not None:
        return STATE_REVIEWING
    return STATE_RECEIVED

# 최종 수정 일 : 2026-10-27
