# 작업자 : 최현준
# 최초 작업 일 : 2026-10-30
"""shoot 테이블에 보관된 구장 사진을 조회만 하는 API."""
import logging

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import Response

from ..database import connect

router = APIRouter()
logger = logging.getLogger(__name__)
ERRORS = {
    404: {"description": "구장 또는 사진이 존재하지 않음"},
    422: {"description": "구장 번호, 사진 번호 또는 페이지 범위가 올바르지 않음"},
    500: {"description": "사진 DB 조회 오류"},
}


@router.get('/{g_code}/photos', summary='구장의 사진 목록 조회', responses=ERRORS)
def list_ground_photos(
    g_code: int = Path(gt=0, description='구장 번호'),
    offset: int = Query(0, ge=0, description='목록 시작 위치'),
    limit: int = Query(50, ge=1, le=100, description='최대 조회 건수'),
):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 사진이 없는 구장은 빈 목록, 존재하지 않는 구장은 404로 구분합니다.
            cursor.execute('SELECT g_code FROM ground WHERE g_code = %s', (g_code,))
            if cursor.fetchone() is None:
                raise HTTPException(404, '존재하지 않는 구장입니다.')
            # 원본 BLOB을 목록에 포함하지 않아 목록 응답 크기를 줄입니다.
            cursor.execute('''SELECT shoot_seq, s_date FROM shoot
                WHERE g_code = %s AND s_image IS NOT NULL AND OCTET_LENGTH(s_image) > 0
                ORDER BY s_date DESC, shoot_seq DESC LIMIT %s OFFSET %s''',
                (g_code, limit, offset))
            rows = cursor.fetchall()
        return {'results': [
            {'shoot_seq': row['shoot_seq'], 's_date': row['s_date'],
             'image_path': f"/ground/{g_code}/photos/{row['shoot_seq']}"}
            for row in rows
        ], 'offset': offset, 'limit': limit}
    except HTTPException:
        raise
    except Exception:
        logger.error('구장 사진 목록 조회 실패')
        raise HTTPException(500, '구장 사진 목록 조회에 실패했습니다.') from None
    finally:
        if connection is not None:
            connection.close()


@router.get('/{g_code}/photos/{shoot_seq}', summary='구장 사진 이미지 조회', responses={
    **ERRORS, 415: {'description': '지원하지 않는 이미지 데이터 형식'},
})
def get_ground_photo(
    g_code: int = Path(gt=0, description='구장 번호'),
    shoot_seq: int = Path(gt=0, description='사진 번호'),
):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 구장 번호와 사진 번호를 함께 확인해 다른 구장 사진과 혼동하지 않습니다.
            cursor.execute('SELECT s_image FROM shoot WHERE g_code = %s AND shoot_seq = %s',
                           (g_code, shoot_seq))
            row = cursor.fetchone()
        if not row or not row['s_image']:
            raise HTTPException(404, '구장 사진이 없습니다.')
        image = row['s_image']
        if not isinstance(image, bytes):
            raise HTTPException(415, '지원하지 않는 이미지 형식입니다.')
        # 확장자가 아닌 데이터 서명을 기준으로 응답 타입을 정합니다.
        if image.startswith(b'\xff\xd8\xff'):
            media_type = 'image/jpeg'
        elif image.startswith(b'\x89PNG\r\n\x1a\n'):
            media_type = 'image/png'
        elif image.startswith((b'GIF87a', b'GIF89a')):
            media_type = 'image/gif'
        elif len(image) >= 12 and image[:4] == b'RIFF' and image[8:12] == b'WEBP':
            media_type = 'image/webp'
        else:
            raise HTTPException(415, '지원하지 않는 이미지 형식입니다.')
        return Response(content=image, media_type=media_type,
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    except HTTPException:
        raise
    except Exception:
        logger.error('구장 사진 조회 실패')
        raise HTTPException(500, '구장 사진 조회에 실패했습니다.') from None
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
