# bootcamp_project_gongin_admin_app

## 팀 매칭 출전 명단 (2026-10-30 / 최현준)

- 공고 팀과 신청 팀의 팀장이 승인된 팀원 중 구장 정원(`ground.g_num`)의 절반을 각각 선택합니다. 정원이 없거나 홀수이면 진행할 수 없습니다.
- 팀장 대표 구장대여는 결제용으로 유지하며, 팀장이 출전하면 이 예약을 재사용합니다. 나머지 선택 팀원은 같은 구장·날짜·시간의 `reservation_category='2'`, `r_check=0` 예약으로 저장합니다. 수락 시 두 팀의 출전자와 대표 예약을 `r_check=1`로 변경합니다. 대표가 출전하지 않으면 시간대 예약 행에 대표 예약도 포함되므로 출전자 집계는 확정 명단 API를 사용해야 합니다.
- 출전자 예약 번호와 신청 당시 팀·회원 정보는 기존 공고·신청 댓글에 숨김 연결 정보로 보관합니다. 거절 또는 다른 팀이 수락되면 해당 대기 신청의 출전자 예약만 삭제하며, 대여 취소 시 남은 대기 출전자 예약도 삭제합니다.
- 출전자 예약의 별도 결제·일반 대여 취소를 차단하고, 일반 대여 목록에서 제외합니다. 기존 공고·신청에는 명단이 없으므로 새 방식의 수락은 불가능하며 재작성·재신청이 필요합니다.
- `/team_match/lineup-options`로 선택 가능한 팀원과 필요 인원을 조회하고, `/team_match/confirmed/{r_seq}`로 확정된 경기의 양 팀 출전자 예약을 조회합니다. 조회는 현재 서비스 JWT를 가진 경기 참여자·해당 팀장만 가능합니다. 매니저 인증과 매니저 앱 연동은 별도 구현이 필요합니다.
- 응답 없이 경기 시간이 지난 대기 공고를 자동 정리하는 스케줄러는 아직 연결되지 않았습니다. 거절·다른 신청 수락·대표 대여 취소 시에만 대기 출전 예약이 정리됩니다.

## 종목별 회원정보·삭제·복구 백엔드 (2026-10-29 / 최현준)

`/auth/account` 하위에 프로필 수정·종목 추가·삭제 신청·30일 내 복구 API를 추가했습니다.
전 종목 비활성 계정은 일반/간편로그인 후 정상 서비스 토큰 대신 복구 전용 토큰을 받습니다.
후속 승인으로 MY 프로필 카드의 수정 화면·계정 삭제 안내/동의 Dialog·로그인 복구 확인을 연결했습니다.
회원정보 수정에서 4개 선호 종목의 기존 선택 표시·신규 추가·해제·유예 종목 복구를 한 번에 저장합니다.
실제 DB 쓰기와 자동 정리 스케줄 등록은 실행하지 않았으며, 실물 화면/연동 검증은 필요합니다.
기존 FK 이력이 남은 계정의 영구 삭제/동일 종목 재가입 및 기존 API 전체의 비활성 회원 차단은 후속 결정이 필요합니다.
완료 범위·Swagger 절차·제약은 [백엔드 프로세스 문서](docs/account_lifecycle_backend.md)를 참고하세요.

## 모바일 로그인 설정 정리 (2026-10-29 / 최현준)

현재 설정 절차는 [개발자 로그인 설정](docs/developer_login_setup.md)을 따릅니다.
`python3 tools/prepare_mobile_config.py`가 `.env`의 모바일 허용 목록과 Firebase iOS plist에서
Git 제외된 실행 JSON/xcconfig를 생성합니다. Google iOS ID를 Dart에 중복 입력하지 않습니다.
VS Code의 `공IN 회원앱 (로컬 설정)`은 실행 전에 동기화하며, 터미널 실행은 위 명령을 먼저 실행합니다.
실물 Google 로그인은 사용자 정상 동작 보고가 있으나 독립적인 재현 검증은 미완료입니다.
카카오·네이버 및 실물 채팅 실패는 담당자와 후속 확인이 필요하며 정상 동작 완료로 간주하지 않습니다.

## GitHub 공유 시 제외하는 로컬 설정

실제 `.env`, `config/social.local.json`, `ios/Flutter/Social.local.xcconfig`, `Signing.local.xcconfig`, 서비스 계정 JSON, `google-services.json`, `GoogleService-Info.plist`는 업로드하지 않습니다. `lib/firebase_options.dart`는 서버 비밀키가 아닌 Firebase 클라이언트 설정이며 필수 import이므로 저장소에 공유합니다. 새 환경은 `.env.example`과 `config/social.example.json`을 참고해 로컬 설정을 준비하고 플랫폼별 Firebase 설정 파일은 별도로 받아야 합니다. 특히 iOS Google 로그인은 로그인용 ID가 포함된 plist가 필요합니다. 이 수정은 Dart 파일 누락을 해결하며 모든 플랫폼의 네이티브 빌드·로그인 성공을 보장하지 않습니다. 비밀값을 소스나 PR 본문에 붙이지 마세요. 공유 정책 수정: 2026-10-29 / 작업자: 최현준.

IDE 기본 실행 설정(2026-10-28 / 양태건): 실행 구성 `공IN 회원앱 (로컬 설정)`은 `config/social.local.json`을 자동으로 읽습니다. 기기를 선택해 F5로 실행하세요. 해당 파일은 Git 제외 대상이며 다른 개발자는 `config/social.example.json`을 참고해 본인 서버 주소·모바일 SDK 키로 작성해야 합니다. 일반 `flutter run` 명령에는 여전히 `--dart-define-from-file=config/social.local.json` 옵션이 필요합니다. FastAPI는 앱과 별도 서버이며 이미 실행 중인 서버를 중복 시작하지 않습니다. 모바일 키·iOS 콜백 설정이 누락되면 간편 로그인은 안내 후 차단됩니다. 서버 `.env` 전체나 서버 비밀키를 앱으로 복사하지 마세요.

간편 로그인 종료 방어 수정(2026-10-28 / 최현준): SDK 호출 전 iOS 앱의 실제 Client ID·콜백 스킴과 공급자별 키를 확인합니다. 누락·취소·SDK 오류·서버 오류 안내를 분리하고 재시도·중복 호출을 점검했습니다. Flutter 가상 테스트 61개와 수정 Dart 정적 검사가 통과했으며, 실제 공급자 인증은 별도 검증이 필요합니다.
위 수정의 iOS 시뮬레이터 빌드도 통과했습니다. Swift 변경이 포함되어 실물폰에는 앱 전체 재빌드·재설치가 필요합니다.

실물 iPhone 테스트 서명(2026-10-28 / 최현준): `ios/Flutter/Signing.local.xcconfig`의 `DEVELOPMENT_TEAM`과 자동 서명을 사용합니다. 해당 파일은 Git 제외 대상이며 각 개발자는 본인 팀으로 설정합니다. 공용 Bundle ID와 Firebase 설정은 변경하지 않았습니다.

## 모바일 간편 로그인·푸시 연결 (작업자: 최현준 / 작업일: 2026-10-28)

2026-10-28 iOS 호환 조합: `firebase_core 4.15.2`, `firebase_auth 6.7.1`, `firebase_messaging 16.7.1`로 고정하고 `google_sign_in 7.2.0`은 유지했습니다.
pub.dev 전체 최신은 Firebase 5.1.0/7.0.1/17.0.1이지만 Google iOS 플러그인의 네이티브 9.x 요구와 충돌하므로, Firebase iOS SDK 12.19.3을 쓰는 최신 이전 메이저 패치를 사용합니다. 실제 계정 인증/푸시 수신은 빌드 검증과 별개입니다. 작업자: 최현준.
검증: Flutter 48개 테스트·변경 관련 정적 검사 통과, iOS 시뮬레이터 빌드 및 iPhone 18 Pro(iOS 27.0) 시작 화면 표시 확인. SPM은 Firebase 12.19.3 / GoogleSignIn 9.2.0 / GTMSessionFetcher 3.5.0으로 해결됐습니다. 네이버 SDK의 CocoaPods 병행 경고와 미설정 iOS APNs entitlement 경고는 남아 있으며, 실제 간편 로그인·푸시는 실행하지 않았습니다.

로그인 아래 Google·카카오·네이버 버튼과 기존 가입 화면을 연결했습니다.
Android FCM 권한·기기 등록/갱신/해제·수신 안내·기존 화면 이동 및 모든 가입 종목 수신을 구현했습니다.
Backend mock 205개, Flutter 48개가 통과했습니다. 실제 로그인·알림 수신은 콘솔/기기 설정 후 검증해야 합니다.
Android debug APK 빌드도 성공했습니다.
2026-10-28 로그인 버튼을 `assets/images/`의 공급자별 이미지로 연결했습니다. 인증 로직은 유지하고 잘못된 에셋 경로를 수정했습니다. 작업자: 최현준.
[설정 파일·실행 방법·미검증 사항](docs/mobile_auth_notification_setup.md)을 확인하세요.

## Backend 전체 검증 (작업자: 최현준 / 작업일: 2026-10-28)

후속 승인 조치: main에 `/report/insert`, `/report/list`를 연결하고 일반 회원가입의
전화번호·성별·팀명 최대 길이를 실제 DB 기준 20/10/50자로 수정했습니다.
예약 구분이 빈 더미 데이터는 건너뛰고 DB를 변경하지 않았습니다.
추가 승인으로 예약·결제·대여 API의 회원 ID 제한을 50자로 맞췄습니다. 예약 분류는 문자열 `"1"`(실력 매칭)·`"2"`(구장 대여)로 통일했습니다. 백엔드 mock 테스트 201개가 통과했으며, 빈 더미 값과 실제 DB 데이터는 변경하지 않았습니다.

PR #1~#26과 현재 `.env` 연결 DB 구조를 대조했습니다. 기존 자동 테스트 187개는 통과했으나,
실제 varchar 자료형을 반영한 추가 mock 검증에서 대여·결제 분기 오류, 소셜 ID 길이 제한,
신고 router 미등록 및 입력 길이/DB 차이를 확인했습니다. **전체 정상 판정은 아닙니다.**
[검증 범위·PR 대응·수정 필요 사항](docs/backend_audit_20261028.md)에 상세 기록했습니다.
실제 DB 쓰기·외부 인증·푸시 발송 및 Backend 수정은 진행하지 않았습니다.

## 알림 Backend 1차 (작업자: 최현준 / 최초 작업 일·최종 수정 일: 2026-10-28)

채팅 수신자 알림, 개인 실력 매치 성사, 경기 시작 10분 전·10분 후 알림을 구현했습니다.
10분 후는 예약별 최신 출석값이 정확히 0인 회원만 대상이며 NULL·기록 없음은 제외합니다.
업무 저장과 DB 이벤트 기록을 같은 트랜잭션으로 처리하고, 별도 worker가 활성 Android 기기로 FCM을 보냅니다.
본인 발송 상태는 JWT 인증 후 `GET /notifications/events`로 조회합니다.
수신은 현재 등록된 정확한 종목별 `c_id_seq` 기준이며 팀 매칭·iOS·웹·Front 연결은 이번 범위 밖입니다.
main 서버 실행만으로 발송하지 않습니다. [알림 실행·검증 안내](docs/notification_phase1.md)를 확인하세요.
신규 알림 모의 테스트 19개 포함 총 77개와 정적 검사·Swagger/health 확인을 통과했습니다.
실제 DB는 읽기 전용 점검만 수행했고 실제 푸시/DB 테스트 데이터는 생성하지 않았습니다.

## 전체 회원 목업 적용 (2026-10-28 / 작업자 : 양태건)

시작·로그인·2단계 회원가입, 구장 상세·개인 예약·전체 대여·결제, 예약 상세,
팀 개설·상세, 대여 경기 매칭 글쓰기, MY·경기 결과·제재·이의신청을 현재 API와 연결했습니다.
화면별 구현 범위와 API가 없는 항목은 [화면/API 대응표](docs/FRONTEND_SCREENS.md)에 정리했습니다.
Python과 실제 DB는 변경하지 않았습니다.

## 회원 프론트엔드 연동 (2026-10-27 / 작업자 : 양태건)

현재 코드는 아래 기능을 제공합니다. 아래쪽 Version 1 설명은 과거 작업 기록입니다.

- 홈: 첨부 목업의 흰 배경·파란 배너·초록 종목 선택·이모지 바로가기·둥근 필터·행 목록 적용. 검색 아이콘으로 구장명/주소 입력을 열고 실제 결과 수와 운영시간을 표시. Riverpod 조회 캐시와 공통 API 주소 사용.
- 하단 탭: 홈, 예약, 팀, 메시지, MY. 게시판·팀 매치 게시글은 홈 바로가기, 문의는 MY 또는 회원 메뉴, 공지는 상단 알림 버튼에서 진입.
- 팀: 목록 검색·페이지 조회, 개설, 가입 신청·팀장 승인/거절, 탈퇴, 팀장 폐지. 가입 상태·팀장 권한은 서버에서 최종 검증.
- 게시판(2026-10-28 / 작업자 : 양태건): 종목 탭·분류 칩·최신 글 강조와 목록, 작성자·본문·조회 수·계층 댓글 상세, 하단 댓글 입력. 선택한 분류를 글쓰기에 유지. 연결된 예약이 있는 매칭신청 글은 실제 경기 정보·신청/수락/거절을 제공하고 성사 후 댓글을 차단. 공감·스크랩·HOT 순위·목록 본문 미리보기는 현재 API에 없어 표시하지 않음.
- 매칭신청 목록: 오른쪽 `매칭신청`으로 직접 신청하고, 작성 팀장은 `신청 목록`에서 받은 팀을 수락·거절. 상대 팀장 응답 대기 중에는 중복 신청 차단. 팀원모집 상세에서는 추가된 tr_state 기반 API로 가입 신청과 현재 팀장의 승인·거절을 처리함. 같은 팀의 모집 글은 회원·팀별 최신 신청 상태를 공유함.
- 채팅: 별도 비밀번호 인증, 방 목록·생성, 방장 초대·종료, 일반 참여자 나가기, WebSocket 메시지와 과거 이력 조회. 토큰은 메모리에만 보관하며 종목 변경·로그아웃 시 폐기.
- 공지: 서버 분류별 목록과 내용 조회. 예약번호가 연결된 기존 게시글의 매칭 신청·수락·거절을 지원합니다. 구장 전체 대여와 예약을 연결한 매칭 게시글 생성 UI, 제재·이의신청 UI는 이번 구현 범위에 포함하지 않았습니다.

채팅에서 연결이 끊기면 방의 다시 연결 버튼을 사용합니다. 인증이 만료되었으면 목록으로 돌아가 다시 로그인합니다. 저장 확인이 없는 메시지는 입력을 보존하며 자동 재전송하지 않습니다. 그룹별 읽음 수·초대 수락·실제 PG 처리는 제공하지 않습니다.

검증 명령: `flutter test`, `flutter analyze`, `flutter build web --debug`.
Mock HTTP·WebSocket 검증은 실제 서버·DB·기기 검증과 구분합니다. 실제 DB를 변경하는 테스트는 실행하지 않습니다.


## 간편 로그인 Backend (작업자: 최현준 / 최초 작업 일·최종 수정 일: 2026-10-28)

`.env.example`에 Firebase Google·카카오·네이버 로그인 설정 항목을 추가했습니다.
2026-10-28 최소 설정 정리: Google은 기존 Firebase 2개, 카카오·네이버는 서버 REST용 각 3개만 유지합니다.
별도 Google Client ID 환경변수와 카카오 모바일·웹 SDK 키는 제거했으며 JWT·DB 설정은 유지합니다.
발급 위치, 공개/비밀 설정 구분, 플랫폼별 준비 및 미구현 범위는
[간편 로그인 설정 안내](docs/social_login_setup.md)를 참고하세요.
Google·카카오·네이버를 별도 router로 구현했습니다. 기존 회원은 서비스 JWT를 발급하고,
신규 회원은 일회용 가입 티켓으로 추가 정보를 입력해 종목별 customer 행을 생성합니다.
PK는 `g_`/`k_`/`n_` + 전체 SHA-256의 URL-safe Base64 + `_01`~`_04`로 총 48자입니다.
`c_login_type`을 저장하고 `c_pw`에는 `간편로그인_비밀번호미지원`, 레이팅에는 1500을 넣습니다.
일반·채팅 비밀번호 로그인은 local 회원만 허용합니다. 새 클래스·자동 DB 변경은 없습니다.

모의·회귀 테스트 총 56개, 정적 검사, main Swagger/health 검증을 통과했습니다.
실제 공급자·DB 쓰기·실기기 로그인 및 Flutter 연결은 미검증/미구현입니다.
현재 로그인 대기 상태는 단일 worker 메모리 기준이며 재시작 시 다시 인증해야 합니다.
예약·결제·구장 대여 API의 회원 ID 제한은 사용자 승인으로 50자로 조정해 48자 소셜 PK를 허용합니다.
Swagger 테스트 순서와 콜백 주소는 위 안내서에 정리했습니다.

## Firebase SDK 연결 (작업자: 최현준 / 작업일: 2026-10-27)

`gongin-4823a` 프로젝트에 Android·iOS·Web 앱을 연결합니다.
기존 `firebase_core`, `firebase_messaging` 의존성을 사용하며 `main.dart`에서 플랫폼별
`DefaultFirebaseOptions`로 Firebase 초기화 후 Riverpod 앱을 실행합니다.

현재 앱 식별자(Android의 `com.example.bootcamp_project_gongin_admin_app`,
iOS의 `com.example.bootcampProjectGonginAdminApp`)는 유지했습니다.
SDK 설정 파일은 클라이언트 식별용이며 서비스 계정 키를 앱에 포함하면 안 됩니다.

이번 범위는 SDK 연결입니다. 경기 시작 로컬 알림, 권한 요청, 회원별 FCM 토큰 등록·갱신,
서버 발송 및 메시지 처리는 별도로 구현해야 합니다.
iOS 푸시에는 Apple Developer의 APNs 키 등록과 Push Notifications/Background Modes 설정,
Web 푸시에는 VAPID 키·서비스 워커·HTTPS 설정이 추가로 필요합니다.

새 개발 환경에서 플랫폼 설정을 다시 내려받으려면 `flutterfire configure --project=gongin-4823a --platforms=android,ios,web`를 실행합니다.
`android/app/google-services.json`은 기존 Git ignore 규칙에 따라 로컬에서 생성되므로 새 환경에서도 재생성이 필요합니다.
공식 설정 안내: https://firebase.google.com/docs/flutter/setup

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

### 개인 채팅방 및 실시간 메시지 (2026-10-27, 양태건)

`python/FastAPI/chat/chat.py`는 기능별 router를 통합하고 `__init__.py`가 이를 main.py에 제공합니다.
요청 모델과 해당 API는 같은 파일에 정의하며, 파일당 클래스 정의는 최대 하나입니다.

- `chat_login_request.py`: `ChatLoginRequest`와 채팅 토큰 발급 router
- `create_room_request.py`: `CreateRoomRequest`와 방 생성 router
- `invite_request.py`: `InviteRequest`와 회원 초대 router
- `socket_message.py`: `SocketMessage`와 메시지 조회·WebSocket 송수신 router
- `chat_room.py`: 공통 인증·DB 처리 및 방 조회·나가기·종료 router
- `chat_request.py`: 공통 요청 설정 클래스 (독립 API 없음)
- `socket_auth.py`: 첫 WebSocket 인증 프레임 클래스 (인증은 같은 WebSocket 안에서 처리)
- `connection_manager.py`: 실시간 연결 관리 클래스 (독립 API 없음)

현재 `messenger`, `participate`, `send_message`를 그대로 사용하며 DB 변경은 필요하지 않습니다.
기본 방 이름은 회원의 `customer.c_team`이고, 무소속이면 `회원이름님의 채팅방`입니다.
생성자가 최초 참여자로 등록되어 방장이 됩니다. 팀 테이블의 팀장 권한과는 별개입니다.

채팅 추가 패키지 설치:

```bash
python3 -m pip install -r python/requirements-chat.txt
```

1. `POST /chat/token`에 종목별 회원 ID(`member_01`)와 `c_pw`를 보내 채팅용 토큰을 받습니다.
2. Swagger **Authorize** 또는 HTTP `Authorization: Bearer 토큰`에 토큰을 설정합니다.
3. `POST /chat/rooms`에 `{}`를 보내 기본 이름의 방을 만듭니다. `me_name`으로 다른 이름도 지정할 수 있습니다.
4. 방장이 `POST /chat/rooms/{me_id}/invite`에 `{"member_ids": ["other_01"]}`를 보내 즉시 초대합니다.
5. `GET /chat/rooms`, `GET /chat/rooms/{me_id}`로 자신의 방과 참여자를 조회합니다.
6. WebSocket 클라이언트로 `ws://서버주소:8000/chat/ws/{me_id}`에 연결합니다.

WebSocket 연결 후 10초 안에 아래 인증 프레임을 보냅니다. 토큰은 URL에 넣지 않습니다.

```json
{"type": "auth", "access_token": "채팅용 토큰"}
```

서버가 `{"type":"ready", ...}`를 응답한 다음 메시지를 보냅니다.

```json
{"type": "message", "content": "안녕하세요!"}
```

메시지는 MySQL 저장·commit에 성공한 뒤 같은 방의 연결된 참여자들에게 전달됩니다.
응답은 `{"type":"message","message":{...}}`이고,
메시지 ID(`s_me_id`)·방 ID·발신 회원 ID·이름·내용·전송 시각이 포함됩니다.
클라이언트가 발신 회원을 지정할 수 없으며 서버는 인증 토큰의 회원 ID를 사용합니다.
동기 PyMySQL 작업은 WebSocket 이벤트 루프를 막지 않도록 스레드에서 실행합니다.
Swagger는 일반 HTTP API 테스트용이며 WebSocket은 별도 클라이언트가 필요합니다.

- 최근 메시지: `GET /chat/rooms/{me_id}/messages?limit=50`
- 과거 메시지: `GET /chat/rooms/{me_id}/messages?before_id=메시지ID`
- 재접속 후 누락 조회: `GET /chat/rooms/{me_id}/messages?after_id=마지막메시지ID`
- 페이지당 최대 100건이며, 응답은 오래된 메시지부터 정렬됩니다. 다음 페이지는 받은 메시지 번호로 요청합니다.
- 내 화면의 중복 표시는 `s_me_id`로 제거할 수 있습니다. 연결 실패 후 같은 내용을 다시 보내면 별도 메시지로 저장될 수 있습니다.
- 나가기: `DELETE /chat/rooms/{me_id}/leave`. 방장은 나갈 수 없고 최초 참여 기록이 유지됩니다.
- 방 종료: 방장만 `DELETE /chat/rooms/{me_id}`. 상태를 `종료`로 바꾸고 대화·참여 기록은 보존합니다.
- 나가기/종료 후 송신은 즉시 차단하며, 기존 연결은 후속 메시지 또는 최대 30초 주기 검사에서 종료됩니다.
- 초대·재초대된 참여자는 이전 대화 전체를 조회할 수 있습니다. 현재 스키마에는 가입 시각·이력 제한 정보가 없습니다.
- `s_me_confirm`은 기본값 0으로 보존하며 개인별 읽음 여부·안 읽은 인원 수는 제공하지 않습니다.
- 채팅은 `c_id_seq`별로 참여하므로 같은 회원이라도 `member_01`과 `member_03`은 서로 다른 참여 ID입니다.

토큰은 30분 후 만료됩니다. 기존 `/auth/login` API는 변경하지 않고 채팅 토큰을 따로 발급합니다.
서버 환경변수 `CHAT_TOKEN_SECRET`에 충분히 긴 비밀키(32바이트 이상 권장)를 지정할 수 있습니다.
지정하지 않으면 프로세스 시작마다 임시 키가 생성되므로 재시작하면 기존 토큰으로 접속할 수 없습니다.
실시간 연결은 **단일 서버 프로세스/worker** 기준입니다. 여러 worker로 확장하려면 Redis 등의 공유 방송 계층이 필요합니다.
앱 채팅 화면은 이번 Backend 구현에 포함하지 않습니다.

테스트는 실제 채팅방·참여자·메시지를 생성하지 않고 모의 DB와 WebSocket TestClient로 검증합니다.

```bash
python3 -m unittest discover -s python/tests -p test_chat.py -v
```
# 일반 로그인 JWT · FCM 기기 등록 (2026-10-27)

작업자 : 최현준 / 최초 작업 일 : 2026-10-27 / 최종 수정 일 : 2026-10-27

알림 Backend의 공통 인증·기기 등록 구동 방식을 문서화했습니다.
새 Python 클래스 없이 함수와 router로 구현했으며 기존 SDK 연결 변경은 보존했습니다.

- `/auth/login`의 기존 응답 필드를 유지하고 `access_token`, `token_type`, `expires_in`(1,800초),
  `c_id_seq`, `member_ids`를 추가했습니다. 탈퇴한 회원은 제외하며 종목별 PK `_01`~`_04`만 정확히 조회합니다.
- 프로젝트 루트 `.env`에 `AUTH_TOKEN_SECRET`을 32바이트 이상의 무작위 비밀값으로 설정해야 합니다.
  비밀키는 Git에 올리지 말고, 운영 API 프로세스 간 동일하게 설정합니다. 없으면 로그인 발급은 503입니다.
- 일반 로그인 JWT는 HS256·issuer·audience·필수 claim·만료를 검증합니다.
  기존 채팅 전용 JWT는 유지하고 일반 로그인 JWT도 채팅 HTTP/WebSocket 인증에 사용할 수 있습니다.
  일반 JWT로 채팅 접속 시 종목별 ID는 로그인 응답의 기본 `c_id_seq`입니다.
- 기기 API는 일반 로그인 JWT만 허용합니다. Swagger의 Authorize에 발급받은 JWT를 입력합니다.
  `POST /notifications/devices`에 아래 JSON을 보내며, `c_id_seq` 생략 시 로그인 기본 종목을 사용합니다.

```json
{"f_token": "Flutter에서 발급된 실제 FCM 토큰", "f_platform": "android", "c_id_seq": "member_01"}
```

플랫폼은 `android`, `ios`, `web` 중 하나입니다. `f_token`은 설명 문구가 아니라
Flutter `FirebaseMessaging.instance.getToken()`의 실제 반환값이어야 합니다.
앱은 로그인 후 토큰 등록 및 `onTokenRefresh` 발생 시 재등록을 호출해야 하며 Front 연결은 아직 미구현입니다.
타인 ID는 403, 탈퇴 회원은 404, 입력 오류는 422, DB 오류는 500, 인증 설정 오류는 503으로 구분합니다.
FCM 토큰은 응답이나 오류 로그에 출력하지 않습니다.

- 로그아웃 **전에** `POST /notifications/devices/deactivate`에 `{"f_token":"실제 토큰"}`을 전송합니다.
  본인 소유 기기만 비활성화하며 이미 해제된 토큰 요청도 안전하게 처리합니다.
- 현재 DB의 `f_token` UNIQUE 구조에서는 기기 토큰 하나가 종목별 회원 PK 하나에 연결됩니다.
  재등록은 해당 기기의 소유 연결을 갱신합니다. 여러 기기는 각자 등록할 수 있습니다.
  같은 계정의 다른 종목 알림까지 기기로 전달할지는 사용자 선택 후 발송 단계에서 연결할 예정입니다.
- 이번 구현은 **인증·기기 등록 단계**입니다. 경기·메시지 이벤트 생성, 예약 시간 감시 worker,
  Firebase Admin 실제 발송, Front 자동 등록은 아직 연결하지 않았습니다.
  다른 기존 API의 인증을 일괄 변경하거나 JWT 갱신·폐기 API를 추가하지 않았습니다.
  JWT 유효기간은 30분이며 만료 후 재로그인이 필요합니다. 기기 해제는 JWT 자체를 폐기하지 않습니다.

정적 검사: 변경 Python 파일 `compileall`, `git diff --check` 통과.
가상 동적 검사: 신규 인증·기기 API 테스트 7개와 기존 채팅 회귀 테스트 31개 통과.
실제 main 앱 TestClient에서 `/docs`, `/health` 200 및 알림 API OpenAPI 등록을 확인했습니다.
DB 쓰기·실제 FCM 발송은 하지 않았습니다. TestClient에서 기존 httpx 관련 지원 중단 예고 경고가 있으며,
테스트 실패는 아닙니다.

```bash
python3 -m pip install -r python/requirements-notification.txt
python3 -m unittest discover -s python/tests -p test_notification_auth.py -v
python3 -m unittest discover -s python/tests -p test_chat.py -v
python3 python/FastAPI/main.py
```
