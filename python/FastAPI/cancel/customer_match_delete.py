# 작업자 : 신현진
# 최초 작업 일 : 2026-10-23

# 취소 후 행과 경기일을 유지하고 r_c_category에 사용자가 직접 작성한 사유를 저장합니다.
# 기존 1~3 코드로 저장된 취소 사유도 계속 조회할 수 있습니다.
# 디버그: 실제 DB에 없는 취소일 컬럼을 참조하지 않습니다.
# 작업자 : 양태건 / 최종 수정일 : 2026-10-26
#
# 중간 수정 작성자 - 신현진
# 수정일 2026.10.28
# 회원 직접 취소 = 기타 → 회원이 작성한 사유 글을 r_c_category에 그대로 저장합니다.
#   '1' ~ '3'은 매니저 취소 사유(본사 앱 버튼)라 회원은 고를 수 없고,
#   글로 '1' ~ '3', '0'만 입력하면 매니저 취소·예약 상태로 잘못 보이므로 422로 막습니다.
import logging

import pymysql
from fastapi import APIRouter, HTTPException, Query

from ..match.reservation_status import (
    CANCEL_REASONS,
    RESERVATION_MATCH,
    RESERVATION_RENTAL,
    RESERVED_CANCEL_CODES,
    category_condition,
    cancellation_allowed,
    is_canceled,
    reservation_type_condition,
)
from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)

# 이 파일의 API들을 담는 라우터 (__init__.py에서 cancel_router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)

# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# 예약 구분 값 (reservation.r_category)
CATEGORY_CANCELED = 2   # 취소

# ************************
# 버그 확인 일 : 2026-10-30 / 작업자 : 최현준
# 1. 발생 위치 : 회원 예약 취소 가능 조건
# 2. 내용 : 성사된 경기는 시작 시간과 무관하게 취소가 차단됨
# 3. 조치 : 한국 시간 기준 시작 1시간 전부터 차단하고 성사 슬롯을 재개방
# 4. 테스트 : 시간 경계와 성사 후 취소·상태 갱신 Mock 테스트
# 5. 보완 : 실제 DB·기기 연동 검증 및 알림 재성사 처리 확인 필요
# ************************


# 중간 수정 작성자 - 신현진
# 수정일 2026.10.28
# 회원 예약 1건 취소 (기타 : 회원이 작성한 사유 글을 그대로 저장)
# 예: DELETE /cancel/reservation/9002?c_id_seq=dummy1_01&r_c_category=개인 일정
@router.delete("/reservation/{r_seq}")
def delete_customer_reservation(
    r_seq: int,
    r_c_category: str = Query(min_length=1, max_length=50, description="회원이 작성한 취소 사유 (기타, 최대 50자)"),
    c_id_seq: str = Query(min_length=4, max_length=50, description="취소를 요청한 회원 (본인 확인용)"),
):
    c_id_seq = c_id_seq.strip()  # 앞뒤 공백 제거
    # 사유 글은 앞뒤 공백을 지우고 검사
    #   빈 글 → 422 / 매니저 취소 코드('1' ~ '3')·예약 상태('0')와 같은 글 → 422
    r_c_category = r_c_category.strip()
    if not r_c_category:
        raise HTTPException(status_code=422, detail="취소 사유를 입력해 주세요.")
    if r_c_category in RESERVED_CANCEL_CODES:
        raise HTTPException(status_code=422, detail="취소 사유는 숫자 하나가 아닌 글로 입력해 주세요.")
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            # 예약 생성과 같은 순서로 구장을 먼저 잠가 정원·성사 상태 경합을 방지합니다.
            cursor.execute("SELECT g_code FROM reservation WHERE r_seq = %s", (r_seq,))
            target = cursor.fetchone()
            if target is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 예약 번호입니다.")
            cursor.execute("SELECT g_code FROM ground WHERE g_code = %s FOR UPDATE", (target['g_code'],))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 구장 코드입니다.")
            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 1) 취소할 예약 조회
            # FOR UPDATE : 취소하는 동안 다른 요청이 이 예약을 바꾸지 못하게 잠금
            # reservation_category : 구장대여(2)는 이 API로 취소하지 않도록 구분값도 함께 조회 (2026.10.26 신현진)
            sql = """
                SELECT r_seq, c_id_seq, g_code, r_date, rs_time, r_check, reservation_category, r_category, r_c_category
                FROM reservation
                WHERE r_seq = %s
                FOR UPDATE
            """
            cursor.execute(sql, (r_seq,))  # 값이 1개여도 튜플이라 (r_seq,) 처럼 쉼표 필요
            reservation = cursor.fetchone()  # 1건만 받음 (없으면 None)
            if reservation is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 예약 번호입니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 1-1) 구장대여(reservation_category = 2)는 구장대여 취소 API에서만 취소
            # (실력매칭 취소 규칙 r_check 등과 섞이지 않게 분리)
            # 값이 없으면 DB 기본값과 같은 1(실력매칭)로 봄
            # 수정 일 : 2026-10-28 / 작업자 : 최현준 — 문자열 '2'인 대여도 개인 취소 API에서 차단합니다.
            if reservation.get("reservation_category", RESERVATION_MATCH) == RESERVATION_RENTAL:
                raise HTTPException(
                    status_code=409,
                    detail="구장대여 예약은 /ground/reservation/{r_seq} 에서 취소해 주세요.",
                )

            # 2) 본인 예약인지 확인
            if reservation["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 예약만 취소할 수 있습니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 2-1) 이미 취소된 예약인지 확인 (행을 지우지 않으므로 같은 예약을 두 번 취소하는 것을 막음)
            if is_canceled(reservation):
                raise HTTPException(status_code=409, detail="이미 취소된 예약입니다.")

            # 성사 여부가 아니라 경기 시작 1시간 전부터 취소를 제한합니다.
            if not cancellation_allowed(reservation["r_date"], reservation["rs_time"]):
                raise HTTPException(status_code=409, detail="경기 시작 1시간 전부터는 취소할 수 없습니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 5) 결제 내역 삭제 (결제 전 예약이면 지울 게 없어서 rowcount = 0)
            # 예약 행은 남지만 결제는 환불 처리되므로 pay에서는 삭제
            cursor.execute("SELECT p_seq, p_amount FROM pay WHERE r_seq = %s", (r_seq,))
            payment = cursor.fetchone()  # 환불 금액 안내용 (없으면 None)
            cursor.execute("DELETE FROM pay WHERE r_seq = %s", (r_seq,))

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.28
            # 취소 사유를 남겨 취소 조회에 포함하고 중복 취소를 방지합니다.
            # 회원 직접 취소(기타)이므로 r_c_category = 회원이 작성한 사유 글
            cursor.execute(
                f"""UPDATE reservation
                    SET r_category = %s, r_c_category = %s
                    WHERE r_seq = %s AND {category_condition(False)}""",
                ("2", r_c_category, r_seq),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="이미 취소된 예약입니다.")
            # 성사 이후 한 자리가 취소되면 남은 동일 슬롯도 미성사로 되돌립니다.
            if reservation['r_check']:
                cursor.execute(
                    f"""UPDATE reservation SET r_check=0 WHERE g_code=%s AND r_date=%s AND rs_time=%s
                        AND {category_condition(False)} AND {reservation_type_condition(RESERVATION_MATCH)}""",
                    (reservation['g_code'], reservation['r_date'], reservation['rs_time']),
                )
        # 중간 수정 작성자 - 신현진
        # 수정일 2026.10.28
        # 응답의 취소 사유 : 저장한 글 그대로 ('4'로 보냈으면 "기타")
        connection.commit()  # 결제 삭제 + 예약 취소 상태 변경을 한 번에 확정
        return {
            "result": "OK",
            "r_seq": r_seq,                                              # 취소된 예약번호
            "c_id_seq": c_id_seq,                                        # 취소한 회원
            "r_category": CATEGORY_CANCELED,                             # 변경된 카테고리 (2 취소)
            "r_date": reservation["r_date"],                             # 취소한 경기의 경기일
            "r_c_category": r_c_category,                                # 저장한 취소 사유 (회원이 작성한 글)
            "cancel_reason": CANCEL_REASONS.get(r_c_category, r_c_category),  # 화면 표시용 취소 사유
            "is_refunded": payment is not None,                          # 결제 취소(환불) 여부
            "refund_amount": payment["p_amount"] if payment else 0,      # 환불 금액
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()  # 위에서 만든 404/403/409는 되돌린 뒤 그대로 전달
        raise
    # 중간 수정 작성자 - 신현진
    # 수정일 2026.10.26
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()  # 에러 시 결제 삭제·취소 상태 변경을 모두 되돌림
        logger.exception("예약 취소 DB 처리 실패")
        raise HTTPException(status_code=500, detail="예약 취소 중 DB 오류가 발생했습니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("예약 취소 처리 실패")
        raise HTTPException(status_code=500, detail="예약 취소에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건 / 수정자 : 신현진 (구장대여 예약 취소 분리)
# 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (문자열 예약 분류로 대여 취소 경로 차단)
# 최종 수정 일 : 2026-10-28 / 작업자 : 양태건 / 수정자 : 신현진 (구장대여 예약 취소 분리, 회원 취소 사유 글 검사)
# 최종 수정 일 : 2026-10-29 / 작업자 : 최현준 (main 취소 사유 규칙과 문자열 예약 분류 처리 통합)
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (경기 시작 1시간 전 취소 제한)
