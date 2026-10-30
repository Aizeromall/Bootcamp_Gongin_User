# 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
"""배너 조건·읽기 권한과 이미지 바이너리를 DB mock으로 검증합니다."""
import sqlite3
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.banner import banner


def app_client():
    app = FastAPI()
    app.include_router(banner.router, prefix='/banner')
    return TestClient(app)


def test_list_uses_active_flag_and_inclusive_date_and_no_write():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{'c_image_seq': 1, 'c_start': date(2026, 10, 30), 'c_end': date(2026, 10, 30)}]
    with patch.object(banner, 'connect', return_value=connection), app_client() as api:
        response = api.get('/banner')
        assert response.status_code == 200
        assert response.json()['results'][0]['image_path'] == '/banner/1/image'
        assert api.post('/banner').status_code == 405
        assert api.delete('/banner/1').status_code in (404, 405)
    sql = cursor.execute.call_args.args[0]
    assert 'c.c_boolean = 1' in sql and 'CURDATE() BETWEEN c.c_start AND c.c_end' in sql
    assert sql.lstrip().startswith('SELECT')
    connection.commit.assert_not_called()
    connection.close.assert_called_once()


def test_image_checks_visibility_and_returns_blob():
    data = b'\xff\xd8\xffvirtual-jpeg'
    with patch.object(banner, 'select_rows', return_value=[{'b_image': data}]) as query, app_client() as api:
        response = api.get('/banner/7/image')
        assert response.status_code == 200 and response.content == data
        assert response.headers['content-type'] == 'image/jpeg'
        assert response.headers['cache-control'] == 'no-store'
        sql, args = query.call_args.args
        assert 'c.c_boolean = 1' in sql and 'CURDATE() BETWEEN c.c_start AND c.c_end' in sql
        assert args == (7,)


def test_only_true_between_start_and_end_including_boundaries():
    # 실제 MySQL은 건드리지 않고 같은 SELECT를 메모리 DB의 경계 데이터로 실행합니다.
    database = sqlite3.connect(':memory:', check_same_thread=False)
    database.row_factory = sqlite3.Row
    database.execute('CREATE TABLE choice (c_image_seq INTEGER, b_seq INTEGER, c_boolean INTEGER, c_start TEXT, c_end TEXT)')
    database.execute('CREATE TABLE banner_image (b_seq INTEGER, b_image TEXT)')
    database.executemany('INSERT INTO banner_image VALUES (?,?)', [(i, f'{i}.jpg') for i in range(1, 7)])
    database.executemany('INSERT INTO choice VALUES (?,?,?,?,?)', [
        (1, 1, 1, '2026-10-30', '2026-10-30'),
        (2, 2, 0, '2026-10-29', '2026-10-31'),
        (3, 3, 1, '2026-10-31', '2026-11-01'),
        (4, 4, 1, '2026-10-28', '2026-10-29'),
        (5, 5, 1, None, '2026-10-31'),
        (6, 6, 1, '2026-10-29', '2026-10-31'),
    ])
    def select(sql, params=()):
        return [dict(row) for row in database.execute(sql.replace('CURDATE()', "'2026-10-30'").replace('OCTET_LENGTH', 'LENGTH').replace('%s', '?'), params)]
    try:
        with patch.object(banner, 'select_rows', side_effect=select), app_client() as api:
            assert [row['c_image_seq'] for row in api.get('/banner').json()['results']] == [1, 6]
            assert api.get('/banner/2/image').status_code == 404
            assert api.get('/banner/3/image').status_code == 404
    finally:
        database.close()


def test_inactive_expired_or_missing_image_not_served():
    with patch.object(banner, 'select_rows', return_value=[]), app_client() as api:
        assert api.get('/banner/1/image').status_code == 404
        assert api.get('/banner/0/image').status_code == 422


def test_supported_types_and_invalid_blob():
    cases = [(b'\x89PNG\r\n\x1a\nexample', 'image/png'),
             (b'GIF89aexample', 'image/gif'), (b'RIFF1234WEBPexample', 'image/webp')]
    for data, expected in cases:
        with patch.object(banner, 'select_rows', return_value=[{'b_image': data}]), app_client() as api:
            response = api.get('/banner/1/image')
            assert response.status_code == 200 and response.content == data
            assert response.headers['content-type'] == expected
    for data in (b'old-filename.jpg', b'', 'old-filename.jpg'):
        with patch.object(banner, 'select_rows', return_value=[{'b_image': data}]), app_client() as api:
            assert api.get('/banner/1/image').status_code == 415


def test_empty_list_and_db_failure():
    with patch.object(banner, 'select_rows', return_value=[]), app_client() as api:
        assert api.get('/banner').json() == {'results': []}
    with patch.object(banner, 'connect', side_effect=RuntimeError('secret')), app_client() as api:
        result = api.get('/banner')
        assert result.status_code == 500 and 'secret' not in result.text


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in globals().items()
                              if name.startswith('test_') and callable(fn))

# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
