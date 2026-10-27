# bootcamp_project_gongin_admin_app

## 사용자 공지 조회 API (작업자: 최현준 / 작업일: 2026-10-27)

- `GET /announce`: 사용자 대상 공지 목록. `a_classify`로 분류 필터, `limit`(1~100), `offset`(0 이상)으로 페이지 조회
- `GET /announce/categories`: 사용자 공지에 실제 저장된 분류만 반환. NULL·공백 분류 제외
- `GET /announce/{a_seq}`: 사용자 대상 공지 상세. 매니저·본사 대상 또는 없는 공지는 동일하게 404 반환

모든 SQL은 `a_target='사용자'`를 서버에서 강제합니다. 대상 선택 파라미터와 공지 작성·수정 API는 제공하지 않습니다.
분류는 고정 목록이 아니며 공지/이벤트/운영 등 실제 데이터에 따라 자동 생성됩니다.
분류 없는 사용자 공지도 전체 목록에서는 조회되고 데이터가 없으면 빈 목록을 반환합니다.
실제 `announcement` 테이블과 작성자 `h_id` FK를 읽기 전용으로 확인했으며 테스트 데이터는 DB에 추가하지 않습니다.

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

### 종목별 회원가입 포지션 (2026-10-26, 양태건)

`POST /auth/register`는 `preferred_stocks: [1, 2, 3, 4]`와
`c_position: {"1": "FW", "2": "가드", "3": "투수", "4": "세터"}`를 받습니다.
선택 종목과 포지션 키는 정확히 일치해야 하며 종목에 맞는 포지션만 허용합니다.
4종목 선택 시 `회원ID_01`부터 `회원ID_04`까지 4행을 생성하고,
각 행의 `c_position`에는 해당 종목의 포지션 문자열만 저장합니다.
종목 번호는 축구=1, 농구=2, 야구=3, 배구=4로 고정되므로 야구만 선택해도 `_03`입니다.
DB 스키마 변경은 없으며 기존 회원 데이터는 변경하지 않습니다.
기존 문자열 `c_position` 요청은 422로 거부되므로 앱과 API를 함께 업데이트해야 합니다.

모의 DB 테스트는 FastAPI, PyMySQL, python-dotenv, httpx 설치 환경에서
프로젝트 루트 기준 `python3 -m unittest discover -s python/tests -v`로 실행합니다.

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

### 취소 내역 조회 (2026-10-26, 양태건)

`reservation.r_c_category`에 취소 사유가 있으면 취소 내역으로 분류합니다.
사용자 앱은 취소 사유를 1~50자로 직접 입력받아 앞뒤 공백을 제거한 뒤 저장·표시합니다.
기존 코드 `1`은 정원 미달, `2`는 우천·기상 악화, `3`은 노쇼 및 환불로 표시합니다.
기존 사유 문자열도 표시하며, NULL·공백·`0`은 미등록으로 처리합니다.
기존 `r_category=2` 취소 상태도 유지해서 조회합니다.
`GET /match/reservation/customer/{c_id_seq}?r_category=1`은 예약·결제용,
`r_category=2`는 취소 조회용입니다. 응답의 `cancel_reason`에 사유 표시명이 포함됩니다.

취소 API는 `DELETE /cancel/reservation/{r_seq}`에 `c_id_seq`와 자유 입력
`r_c_category` 쿼리를 필수로 받습니다. 앱에서는 예약·결제 카드의 **예약 취소** 버튼으로
사유를 입력하고 **취소 확정**을 누르면 취소 탭으로 이동합니다.
기존 본인 확인·지난 경기·확정 경기 제한을 유지합니다.
취소일 컬럼을 추가하지 않으며, 경기일과 예약 행은 보존합니다.
매니저는 별도 예약 컬럼 없이 배정표의 요일·시간으로 조회합니다.
테스트는 실제 취소·결제 데이터 변경 없이 모의 DB로 수행합니다.

### 홈 구장 탐색 (2026-10-26, 양태건)

기존 홈에 축구·배구·농구·야구 4칸 GridView와 전체 지역 드롭다운을 제공합니다.
구장 조회 API의 전체 결과를 설명 `g_information`의 `종목: 축구` 같은 명시 정보와
주소의 시·도 기준으로 필터링합니다. 설명에 종목이 없으면 임의 분류하지 않습니다.
이름/주소 검색과 지역·종목 선택을 함께 적용하며, 필터 변경 시 API를 다시 호출하지 않습니다.
탐색 종목은 Riverpod의 `groundSportProvider`, 지역은 `groundRegionProvider`로 관리합니다.
예약·결제 종목과 탐색 상태를 분리하여 미가입 종목도 조회할 수 있고,
예약 직전에는 가입 종목을 확인한 뒤 종목별 회원 ID를 연결합니다.
