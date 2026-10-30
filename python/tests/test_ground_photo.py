# 작업자 : 최현준
# 최초 작업 일 : 2026-10-30
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.ground import ground_photo, ground_router


@pytest.fixture
def setup():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    app = FastAPI()
    app.include_router(ground_router)
    with patch.object(ground_photo, 'connect', return_value=connection), TestClient(app) as client:
        yield client, connection, cursor


def test_list_and_empty_and_unknown_ground(setup):
    client, connection, cursor = setup
    cursor.fetchone.return_value = {'g_code': 2}
    cursor.fetchall.return_value = [{'shoot_seq': 12, 's_date': date(2026, 10, 30)}]
    result = client.get('/ground/2/photos?offset=0&limit=10')
    assert result.status_code == 200
    assert result.json()['results'] == [{'shoot_seq': 12, 's_date': '2026-10-30', 'image_path': '/ground/2/photos/12'}]
    sql, params = cursor.execute.call_args.args
    assert 's_image FROM' not in sql and params == (2, 10, 0)
    cursor.fetchall.return_value = []
    assert client.get('/ground/2/photos').json()['results'] == []
    cursor.fetchone.return_value = None
    assert client.get('/ground/2/photos').status_code == 404
    assert client.get('/ground/2/photos?limit=101').status_code == 422
    connection.close.assert_called()


@pytest.mark.parametrize(('blob', 'mime'), [
    (b'\xff\xd8\xfftest', 'image/jpeg'),
    (b'\x89PNG\r\n\x1a\ntest', 'image/png'),
    (b'GIF89atest', 'image/gif'),
    (b'RIFF1234WEBPtest', 'image/webp'),
])
def test_image_bytes_content_type_and_scoped_lookup(setup, blob, mime):
    client, connection, cursor = setup
    cursor.fetchone.return_value = {'s_image': blob}
    result = client.get('/ground/2/photos/12')
    assert result.status_code == 200 and result.content == blob
    assert result.headers['content-type'] == mime
    assert result.headers['x-content-type-options'] == 'nosniff'
    assert cursor.execute.call_args.args[1] == (2, 12)
    connection.close.assert_called_once()


def test_photo_missing_bad_format_and_db_error(setup):
    client, connection, cursor = setup
    for row in [None, {'s_image': b''}]:
        cursor.fetchone.return_value = row
        assert client.get('/ground/2/photos/12').status_code == 404
    cursor.fetchone.return_value = {'s_image': b'not-image'}
    assert client.get('/ground/2/photos/12').status_code == 415
    assert client.get('/ground/0/photos/12').status_code == 422
    cursor.execute.side_effect = RuntimeError('sensitive details')
    result = client.get('/ground/2/photos/12')
    assert result.status_code == 500 and 'sensitive details' not in result.text
    assert connection.close.call_count == 4


def test_openapi_documents_image_routes(setup):
    client, _, _ = setup
    paths = client.get('/openapi.json').json()['paths']
    assert '/ground/{g_code}/photos' in paths
    assert '/ground/{g_code}/photos/{shoot_seq}' in paths
    assert {'404', '415', '422', '500'} <= paths['/ground/{g_code}/photos/{shoot_seq}']['get']['responses'].keys()
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
