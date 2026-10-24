# bootcamp_project_gongin_admin_app

## 회원 앱 Version 1 (2026-10-24)

로그인 페이지에서 시작하며 회원가입 → 구장 검색 → 날짜별 잔여 자리 선택 → 예약 → 결제 기록 저장,
예약·결제 내역 및 문의 작성·답변 조회를 제공합니다. Python 코드는 변경하지 않았습니다.

```bash
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Android 에뮬레이터에서는 `http://10.0.2.2:8000`, 실제 기기에서는 FastAPI 서버의 LAN 주소를 사용합니다.
Flutter Web은 해당 Origin이 서버 CORS 설정에 허용되어 있어야 합니다. 앱에 서버 `.env`나 DB 비밀번호를 넣지 않습니다.

- `lib/main.dart`: Riverpod ProviderScope 및 앱 진입점
- `lib/app.dart`: 테마와 로그인 상태에 따른 첫 화면
- `lib/service/member_api.dart`: HTTP 통신, 시간 제한, 서버 오류 메시지 처리
- `lib/vm/member_state.dart`: 회원·선택 종목 Riverpod 상태
- `lib/view/auth`, `ground`, `reservation`, `payment`, `history`, `inquiry`, `home`, `shared`: 화면별 구성

로그인 응답의 가입 종목 코드로 회원 FK를 구성합니다. 구장 API에 종목 속성이 없어 종목별 구장 필터는 제공하지 않습니다.
실제 PG 승인·출금, 토큰 인증, 팀 생성·가입, 레이팅 변경은 Version 1 범위에 포함하지 않습니다.
결제는 기록 저장 기능임을 화면에서 안내하며, 결제를 미룬 예약은 예약 내역에서 이어서 진행합니다.
회원가입에서는 현재 서버 필수 필드인 팀·포지션을 입력받고 레이팅을 임의 설정하지 않습니다.

검증: `flutter test`, 새 파일 대상 `flutter analyze`. 최종 화면과 실제 서버 연동은 사용자가 실행하여 확인합니다.

### 작업 및 PR 기록

- 작업자: 최현준
- 작업일: 2026-10-24
- PR 본문에는 작업자·작업일·작업 내용·정적 검증 내용·미검증 항목을 기록합니다.
- 현재 DB 서버 연결이 되지 않아 실제 DB를 이용한 로그인·회원가입·예약·결제·문의 연동 검증은 완료하지 못했습니다.
  가상 HTTP 응답 기반 테스트는 실제 DB 연동 검증과 구분합니다.

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
