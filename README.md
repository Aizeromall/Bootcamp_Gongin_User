# bootcamp_project_gongin_admin_app

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter learning resources](https://docs.flutter.dev/reference/learning-resources)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## FastAPI 인증 API

`python/FastAPI/auth`에 회원가입과 로그인 라우터를 분리했습니다.

- `register.py`: `POST /register` — 종목별 customer 레코드를 생성합니다.
- `login.py`: `POST /login` — `c_id_seq`, `c_pw` 기반의 로그인 정보를 검증합니다.
- `auth/__init__.py`: `login_router`, `register_router`를 내보냅니다. 서버 시작 파일에서
  `app.include_router(login_router, prefix="/auth")` 및
  `app.include_router(register_router, prefix="/auth")`로 연결합니다.

### 서버 실행

`python/FastAPI/main.py`가 서버 진입점이며, DB 연결은 `python/FastAPI/database.py`가 담당합니다.
프로젝트 루트 `.env`에 `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`,
`API_HOST`, `API_PORT`를 설정한 뒤 아래 명령으로 실행합니다.

```bash
python3 python/FastAPI/main.py
```

모듈 방식도 지원합니다: `cd python && python3 -m FastAPI.main`

실행 후 Swagger 페이지는 `http://<API_HOST>:<API_PORT>/docs`, 상태 확인은
`http://<API_HOST>:<API_PORT>/health`에서 확인할 수 있습니다.
