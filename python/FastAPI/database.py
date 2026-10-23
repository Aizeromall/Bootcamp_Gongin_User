# 작업자 : 최현준
# 최초 작업 일 : 2026-10-23

import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv

# database.py → FastAPI → python → 프로젝트 루트 순서로 .env를 찾습니다.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def connect() -> pymysql.Connection:
    """.env의 DB 설정으로 MySQL 연결을 반환

    연결은 API 요청 시점에만 생성하므로 Swagger와 health endpoint는 DB 없이도 열람 가능
    """

    required_names = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    missing_names = [name for name in required_names if not os.getenv(name)]
    if missing_names:
        # 민감한 값은 노출하지 않고, 서버 로그에서만 설정 누락 여부를 확인할 수 있게 합니다.
        raise RuntimeError(f"DB 환경 설정이 누락되었습니다: {', '.join(missing_names)}")

    try:
        db_port = int(os.getenv("DB_PORT", "3306"))
    except ValueError as error:
        raise RuntimeError("DB_PORT는 정수여야 합니다.") from error

    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=db_port,
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
    )

# 최종 수정 일 : 2026-10-23
