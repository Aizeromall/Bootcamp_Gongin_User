# 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
"""현재 게시 중인 배너와 DB 이미지 데이터만 제공하는 읽기 전용 API."""
import logging

from fastapi import APIRouter, HTTPException, Path as ApiPath
from fastapi.responses import Response

from ..database import connect

router = APIRouter()
logger = logging.getLogger(__name__)
ACTIVE = "c.c_boolean = 1 AND c.c_start IS NOT NULL AND c.c_end IS NOT NULL AND CURDATE() BETWEEN c.c_start AND c.c_end"
ERRORS = {500: {"description": "배너 DB 조회 오류"}}


def select_rows(sql, params=()):
    """DB에 쓰지 않고 공개 기간·활성 상태를 조회합니다."""
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())
    except Exception:
        # DB 접속 정보나 파일 경로가 예외 문자열에 섞여도 로그에 남기지 않습니다.
        logger.error('배너 조회 실패')
        raise HTTPException(500, '배너 조회 중 오류가 발생했습니다.') from None
    finally:
        if connection is not None:
            connection.close()


@router.get('', summary='현재 게시 중인 배너 목록 조회', responses=ERRORS)
def list_banners():
    # 시작일·종료일을 포함해 비교하고 false·날짜 NULL은 제외합니다.
    rows = select_rows(f"""SELECT c.c_image_seq, c.c_start, c.c_end
        FROM choice c JOIN banner_image b ON b.b_seq=c.b_seq
        WHERE {ACTIVE} AND b.b_image IS NOT NULL AND OCTET_LENGTH(b.b_image)>0
        ORDER BY c.c_image_seq""")
    return {'results': [
        {'c_image_seq': row['c_image_seq'], 'c_start': row['c_start'], 'c_end': row['c_end'],
         'image_path': f"/banner/{row['c_image_seq']}/image"}
        for row in rows
    ]}


@router.get('/{image_id}/image', summary='게시 중인 배너 이미지 조회', responses={
    404: {'description': '게시 대상이 아니거나 이미지 데이터가 없음'},
    415: {'description': '지원하지 않는 이미지 데이터 형식'},
    422: {'description': '잘못된 배너 번호'},
    **ERRORS,
})
def get_banner_image(image_id: int = ApiPath(gt=0)):
    # 이미지 주소를 직접 알아도 비활성·기간 외 배너는 제공하지 않습니다.
    rows = select_rows(f"""SELECT b.b_image FROM choice c JOIN banner_image b ON b.b_seq=c.b_seq
        WHERE c.c_image_seq=%s AND {ACTIVE} AND b.b_image IS NOT NULL AND OCTET_LENGTH(b.b_image)>0 LIMIT 1""", (image_id,))
    if not rows:
        raise HTTPException(404, '조회할 수 있는 배너 이미지가 없습니다.')
    # DB의 LONGBLOB 내용을 그대로 반환하며 파일명이나 확장자를 신뢰하지 않습니다.
    image = rows[0]['b_image']
    if not isinstance(image, bytes):
        logger.warning('배너 이미지 데이터 타입 오류: image_id=%s', image_id)
        raise HTTPException(415, '지원하지 않는 이미지 데이터입니다.')
    if image.startswith(b'\xff\xd8\xff'):
        media_type = 'image/jpeg'
    elif image.startswith(b'\x89PNG\r\n\x1a\n'):
        media_type = 'image/png'
    elif image.startswith((b'GIF87a', b'GIF89a')):
        media_type = 'image/gif'
    elif len(image) >= 12 and image[:4] == b'RIFF' and image[8:12] == b'WEBP':
        media_type = 'image/webp'
    else:
        logger.warning('배너 이미지 형식 오류: image_id=%s', image_id)
        raise HTTPException(415, '지원하지 않는 이미지 데이터입니다.')
    return Response(content=image, media_type=media_type,
                    headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (DB 이미지 바이너리 직접 조회)
