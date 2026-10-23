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
- `match/reservation.py`: `POST /match/reservation` — 08:00~24:00의 2시간 슬롯으로 구장을 예약합니다.
- `match/payment.py`: `POST /match/payment` — 예약 번호(`r_seq`)로 1인 이용금액을 결제합니다.
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

### 구장 예약 규칙

- `rs_time`은 `08:00`, `10:00`, `12:00`, `14:00`, `16:00`, `18:00`, `20:00`, `22:00`만 선택할 수 있고,
  `re_time`은 각각 정확히 2시간 뒤의 종료 시간으로 서버가 저장합니다.
- `c_id_seq`의 끝 번호 `01`~`04`는 축구·농구·야구·배구 순서입니다.
- 같은 구장·날짜·시간의 예약 수가 `ground.g_num`에 도달하면 해당 슬롯의 `r_check`를 `true`로 갱신하고
  추가 예약을 막습니다.
- 예약 성공 응답의 `r_seq`, 동일한 예약 회원의 `c_id_seq`, 선택한 문자열 결제 수단을 프런트엔드는 `/match/payment`로 전달합니다.
  `p_amount`는 `ground.g_price / ground.g_num`을 원 단위 반올림한 값, `p_date`는 예약의 `r_date`, `p_num`은 `g_code_p_seq`로 저장됩니다.
  서버가 `reservation.c_id_seq` FK와 요청값을 비교한 뒤, 일치할 때만 `pay.c_id_seq` FK를 저장합니다.
