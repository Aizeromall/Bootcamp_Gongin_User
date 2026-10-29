# Google · 카카오 · 네이버 간편 로그인 Backend 및 설정

작업자 : 최현준 / 최초 작업 일 : 2026-10-28

후속 승인 반영: 앱은 모바일 SDK 방식으로 연결하고 `/auth/kakao/mobile`, `/auth/naver/mobile`을 추가했습니다.
기존 REST 브라우저 콜백은 유지합니다. [모바일 키·실행·검증 안내](mobile_auth_notification_setup.md)를 우선 참고하세요.
아래 Flutter 미변경 설명은 최초 Backend 단계 기록입니다.

## 현재 작업 범위

`.env.example`에 로그인 연동용 설정 항목과 주석을 추가했습니다.
선택 환경변수는 `.env.example`과 로컬 `.env`에서 제거하고 기존 필수 설정값은 보존했습니다.
공급자별 router와 신규 간편가입 API를 구현했습니다. 콘솔·실제 DB·Flutter 화면은 변경하지 않았습니다.
Google은 Firebase Admin ID 토큰 검증, 카카오·네이버는 REST 인가 코드 교환을 사용합니다.
Android를 최종 개발 기준으로 하고 iOS는 테스트용으로 사용합니다. 웹은 이번 범위에서 제외합니다.
Google은 Firebase 설정을 재사용하고, 카카오·네이버는 서버 인가 코드 교환에 필요한 항목만 남깁니다.

| 제공자 | 남기는 서버 환경변수 |
| --- | --- |
| Google / Firebase | `FIREBASE_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` |
| 카카오 | `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`, `KAKAO_REDIRECT_URI` |
| 네이버 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `NAVER_REDIRECT_URI` |

`AUTH_TOKEN_SECRET`은 위 제공자 설정과 별개인 우리 서버 JWT 서명키이므로 유지합니다.

## 1. Google: Firebase Authentication

1. [Firebase 콘솔](https://console.firebase.google.com/)에서 기존 `gongin-4823a` 프로젝트를 선택합니다.
2. Authentication → Sign-in method에서 Google을 활성화하고 프로젝트 지원 이메일을 설정합니다.
3. Android: 프로젝트 설정의 Android 앱에 개발/배포 서명 인증서 SHA-1을 등록합니다.
   출시 시 Play App Signing을 사용하면 해당 앱 서명 인증서도 확인합니다.
   변경 후 앱 설정 파일을 다시 내려받아 적용합니다.
4. iOS: 해당 앱의 `GoogleService-Info.plist`를 확인하고 Google 로그인에 필요한 URL scheme을 설정합니다.
5. 서버 `.env`에 `FIREBASE_PROJECT_ID=gongin-4823a`를 입력합니다.
   로컬 개발에서 서비스 계정 JSON을 사용할 경우 `GOOGLE_APPLICATION_CREDENTIALS`에
   해당 JSON의 **서버 내 절대 경로**를 입력합니다. JSON 원문을 넣지 않습니다.
   프로젝트 설정 → 서비스 계정에서 발급할 수 있으며 이미 적절한 서버 자격 증명이 있다면 재발급할 필요가 없습니다.
   운영에서는 가능하면 실행 환경의 기본 자격 증명/관리형 서비스 계정을 사용합니다.

후속 Flutter 구현에는 `firebase_auth`와 모바일 Google 로그인을 위한 `google_sign_in` 등이 필요합니다.
Google Client ID를 위한 별도 `.env` 항목은 두지 않습니다.
앱의 로그인 SDK에 필요한 정보는 Firebase 플랫폼 설정 파일 및 네이티브 설정에서 연결합니다.
환경변수 최소화가 앱 SDK·플랫폼 설정도 필요 없다는 뜻은 아닙니다.
Firebase 방식의 ID 토큰 검증을 위해 Google Client Secret을 추가할 필요는 없습니다.

인증 흐름은 Flutter Google 로그인 → Firebase 로그인 → **Firebase ID 토큰**을 서버에 전달 →
Firebase Admin 검증 → 기존 회원은 서비스 JWT 발급 / 신규 회원은 추가 정보 입력용 티켓 발급입니다.
Google ID 토큰·Firebase ID 토큰·FCM 기기 토큰·서비스 JWT는 서로 다른 용도입니다.

공식 문서: [Flutter Google 로그인](https://firebase.google.com/docs/auth/flutter/federated-auth),
[서버 ID 토큰 검증](https://firebase.google.com/docs/auth/admin/verify-id-tokens)

## 2. 카카오

1. [카카오디벨로퍼스](https://developers.kakao.com/)에서 서비스 앱을 생성하거나 기존 앱을 선택합니다.
2. 카카오 로그인 → 사용 설정을 ON으로 변경합니다.
3. 앱 → 플랫폼 키에서 REST API 키와 해당 Client Secret을 확인하고
   `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`에 입력합니다.
   현재 공식 안내상 새 REST API 키는 Client Secret 기능이 활성화된 상태로 추가됩니다.
   기존 앱도 실제 설정 상태를 확인해 토큰 교환에 필요한 시크릿을 준비합니다.
4. 카카오 로그인 Redirect URI에 구현된 서버 콜백 URL을 등록하고
   `KAKAO_REDIRECT_URI`에도 동일하게 입력합니다.
   개발 주소 예시는 `http://localhost:8000/auth/kakao/callback`입니다.
   콜백 API는 구현되어 있습니다. 운영은 실제 HTTPS 도메인으로 변경해야 합니다.
5. 필요한 동의항목만 설정합니다. 이메일은 사용자 동의/권한에 따라 없을 수 있습니다.
현재는 서버 REST 방식의 세 항목만 준비하며, 다른 SDK 키를 추가하지 않습니다.
로그인만을 위해 관리자(Admin) 키를 추가하거나 앱에 포함하지 않습니다.

공식 문서: [설정하기](https://developers.kakao.com/docs/ko/kakaologin/prerequisite),
[REST API](https://developers.kakao.com/docs/ko/kakaologin/rest-api)

## 3. 네이버

1. [네이버 개발자센터](https://developers.naver.com/apps/#/register)에서 애플리케이션을 등록합니다.
2. 사용 API에 **네이버 로그인**을 선택합니다.
3. 발급된 값을 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`에 입력합니다.
4. 서버 OAuth 흐름에 사용할 서비스 URL과 Callback URL을 등록합니다.
   Callback URL은 `NAVER_REDIRECT_URI`와 실제 요청값이 정확히 같아야 합니다.
   개발 주소 예시는 `http://localhost:8000/auth/naver/callback`이며 해당 콜백 API가 구현되어 있습니다.
   서버 콜백은 모바일에서 시작한 로그인 결과를 서버가 받는 주소이며, 웹 앱을 개발한다는 의미는 아닙니다.
5. 개발 단계에는 테스트 계정으로 확인하고, 일반 사용자 공개 전에는 네이버 로그인 검수를 진행합니다.
   Client Secret은 서버 교환 방식에서 서버에 보관하며 Flutter 공개 설정에 넣지 않습니다.

공식 문서: [네이버 로그인 개발가이드](https://developers.naver.com/docs/login/devguide/devguide.md)

## 보안 및 후속 구현 시 결정 사항

- 서버용 `.env` 전체나 서비스 계정 JSON을 Flutter assets, Git, 로그에 포함하지 않습니다.
  앱에 필요한 공개 식별자만 별도 플랫폼 설정으로 전달합니다.
- 서버는 공급자의 토큰/인가 코드를 검증해야 합니다. Front가 보내는 이메일·회원 ID만 신뢰하지 않습니다.
- 서버 인가 코드 방식은 state와 시작 브라우저의 HttpOnly 쿠키를 함께 확인하며 일회성·10분 만료를 적용합니다.
- Google은 Firebase Authentication을 사용하고, 카카오·네이버는 각 공급자의 API 연동을 준비합니다.
  이 설정만으로 카카오·네이버가 Firebase 로그인 공급자로 자동 등록되지는 않습니다.
- 이메일이 같다는 이유로 기존 일반 회원과 자동 연결하지 않습니다. 기존 회원 연결/병합은 미구현입니다.
- 공급자 ID를 검증한 뒤 `SHA-256(공급자:고유ID)` 전체를 URL-safe Base64로 변환합니다.
  절단하지 않은 43자 해시 앞에 `g_`/`k_`/`n_`, 뒤에 `_01`~`_04`를 붙여 총 48자입니다.
  같은 공급자·고유 ID는 언제나 같은 PK를 생성하며 해시로 원본 ID를 복원할 수 없습니다.
  대소문자 무시 DB collation으로 다른 해시의 행이 조회되면 409로 차단합니다.
- `c_login_type`은 google/kakao/naver, `c_pw`는 `간편로그인_비밀번호미지원`을 저장합니다.
  일반 로그인·기존 채팅 비밀번호 로그인은 local 회원만 허용합니다. 간편회원은 서비스 JWT로 채팅을 인증합니다.
  일반 가입에서 소셜 회원용 접두어 선점을 차단합니다. 일반 회원의 이름·아이디를 자동 변경하지 않습니다.
- 실제 공급자 로그인·콘솔 연결·DB 쓰기·실기기 검증은 수행하지 않았습니다.

## 구현 API 및 Swagger 검증 순서

| 메서드 | 경로 | 역할 |
| --- | --- | --- |
| POST | `/auth/google/login` | Firebase Google ID 토큰 검증 |
| GET | `/auth/kakao/login` | 카카오 인증 URL 발급 및 시작 쿠키 설정 |
| GET | `/auth/kakao/callback` | 카카오 코드 교환·회원 조회 |
| GET | `/auth/naver/login` | 네이버 인증 URL 발급 및 시작 쿠키 설정 |
| GET | `/auth/naver/callback` | 네이버 코드 교환·회원 조회 |
| POST | `/auth/social/register` | 신규 간편회원 추가 정보 저장 및 서비스 JWT 발급 |

1. 의존성을 설치합니다: `python3 -m pip install -r python/requirements-social.txt`.
2. DB에는 사용자가 적용한 `c_login_type ENUM('local','google','kakao','naver') NOT NULL DEFAULT 'local'`이 필요합니다.
   서버 시작 시 자동 DDL·마이그레이션은 실행하지 않습니다.
3. `.env`의 필수 설정과 `AUTH_TOKEN_SECRET`을 준비하고 FastAPI를 실행합니다.
   콜백 경로는 `.env.example`에 기재했습니다. `.env`의 실제 값은 이번 구현에서 변경하지 않았습니다.
4. `/docs`에서 카카오 또는 네이버 `/login`을 실행합니다.
   반환된 `authorization_url`을 **같은 브라우저**에서 열어 실제 공급자 로그인·동의를 진행합니다.
   Swagger·콜백의 호스트를 localhost와 LAN IP로 혼용하면 쿠키가 연결되지 않습니다.
   다른 브라우저/시크릿 창도 시작 쿠키가 없어 콜백이 거절됩니다.
5. 공급자가 콜백을 호출하면 JSON이 반환됩니다. 가입된 회원이면 기존 로그인 형식과 서비스 JWT,
   신규 회원이면 `signup_required=true`, `signup_ticket`, `expires_in=600`이 반환됩니다.
   콜백을 Swagger에서 임의 코드로 재실행하거나 같은 코드를 재사용하는 테스트는 성공할 수 없습니다.
6. Google은 앱에서 획득한 Firebase ID 토큰을 `/auth/google/login`에 다음처럼 전달합니다.

```json
{"id_token": "앱에서 받은 실제 Firebase ID 토큰"}
```

7. 신규 회원은 `/auth/social/register`에 다음 형태로 추가 정보를 보냅니다. 서비스 ID·비밀번호·로그인 방식은 받지 않습니다.

```json
{
  "signup_ticket": "공급자 인증 후 받은 실제 티켓",
  "c_name": "홍길동",
  "c_address": "서울",
  "c_phone": "01012345678",
  "c_gender": "남성",
  "c_birthday": "2000-01-01",
  "preferred_stocks": [1, 3],
  "c_position": {"1": "FW", "3": "투수"}
}
```

검증된 종목별 행은 하나의 트랜잭션으로 생성하며 가입일은 한국 시간의 처리 시점입니다.
`c_team=무소속`, `c_rating=1500`을 서버에서 고정하고 `c_category`는 팀 가입/개설 시 생성할 값이므로 설정하지 않습니다.
입력 오류는 422이며 티켓을 소비하지 않습니다. 유효 입력으로 가입을 시작하면 티켓을 한 번 소비하며,
DB 오류나 중복 가입이면 다시 공급자 인증을 진행해야 합니다. 가입 성공 응답은 201입니다.

## 운영 제한 및 Front 후속 작업

- state·가입 티켓은 잠금으로 보호된 프로세스 메모리에 최대 2,000개·10분간만 보관합니다.
  **현재는 단일 API 프로세스/worker 기준**입니다. 재시작하면 인증을 다시 해야 하며 다중 worker 운영 전에는 공유 저장소가 필요합니다.
- 공급자 access/refresh token과 이메일·프로필 원문은 DB에 저장하지 않습니다. 일반 ID·이메일 계정과의 자동 병합은 없습니다.
- 콜백 응답은 `no-store` JSON이며 JWT를 리다이렉트 URL에 붙이지 않습니다.
  Flutter 로그인 버튼·브라우저 로그인 시작/결과 회수·앱 복귀·추가 가입 화면 연결은 별도 구현이 필요합니다.
  새 `.env` 키나 웹 전용 로그인은 추가하지 않았습니다.
- 운영은 HTTPS로 설정합니다. 프록시 뒤에서 원래 HTTPS 요청이 올바르게 인식되도록 신뢰 프록시를 설정해야
  Secure 쿠키가 적용됩니다. 서버/프록시 access log에는 OAuth 콜백의 code·state 쿼리를 남기지 않도록 설정합니다.
- 연동 점검에서 발견한 예약(`/match/reservation`)·결제(`/match/payment`)·구장 대여 API의 45자 회원 ID 제한은
  사용자 승인으로 50자로 조정했습니다. 48자 소셜 PK와 50자 경계값의 mock 업무 성공, 51자 차단을 확인했습니다.
  소셜 로그인·가입 테스트 통과가 기존 모든 기능의 실연동 완료를 의미하지 않습니다.

## 수행한 검증

- 공급자별 콜백, 가입, 보안 경계 신규 모의 테스트 12개와 기존 인증·기기·채팅·회원가입 테스트 합계 56개 통과.
- `compileall`, `git diff --check` 통과. main 앱 TestClient의 `/docs`, `/health` 200 및 6개 소셜 API OpenAPI 등록 확인.
- 테스트의 공급자 HTTP·Firebase·MySQL은 mock으로 대체했습니다. 실제 DB 데이터는 만들지 않았습니다.
- TestClient의 httpx 지원 중단 예고 경고가 있으나 테스트 실패는 아닙니다.

```bash
python3 -m unittest python.tests.test_social_login python.tests.test_notification_auth python.tests.test_chat python.tests.test_register -v
```

최종 수정 일 : 2026-10-28
