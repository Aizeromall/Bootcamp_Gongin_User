# 회원 앱 화면과 API 연결

작성 일 : 2026-10-28 / 작업자 : 양태건

첨부된 전체 목업의 구성을 현재 FastAPI가 제공하는 기능에 맞춰 적용했습니다.
아래는 화면의 실제 구현 범위이며, API가 없는 기능은 가짜 데이터나 성공 화면으로 대체하지 않습니다.

| 화면 | 구현 위치 | 연결·제한 |
| --- | --- | --- |
| 시작 | `lib/view/auth/welcome_page.dart` | 시작하기 → 로그인 |
| 로그인 | `lib/view/auth/login_page.dart` | `POST /auth/login`, 아이디 로그인 |
| 회원가입 1·2단계 | `lib/view/auth/register_page.dart` | 계정·비밀번호 확인 → 기본 정보·종목별 포지션 → `POST /auth/register` |
| 홈 | `lib/view/ground/grounds_page.dart` | `/ground`, 네 종목·지역·이름/주소 검색 |
| 구장 상세 | `lib/view/ground/ground_detail_page.dart` | `/ground/{g_code}`, 실제 시설 안내·오늘 배정 매니저 |
| 실력 매칭 | `GroundsPage(matchOnly:true)` | 구장 선택 → 개인 자리 예약. 레벨 추천 API는 없음 |
| 개인 자리 예약 | `lib/view/reservation/reservation_page.dart` | `/match/reservation/ground/{g_code}`, `POST /match/reservation` |
| 구장 전체 대여 | `ReservationPage(rental:true)` | `/ground/reservation/slots/{g_code}`, `POST /ground/reservation` |
| 결제 | `lib/view/payment/payment_page.dart` | `POST /match/payment`. 실제 PG 승인·출금은 없음 |
| 예약·결제·취소 | `lib/view/history/history_page.dart` | 회원별 조회, 결제번호 연결, 사유 입력 취소. Riverpod `historyProvider` |
| 예약 상세 | `lib/view/history/reservation_detail_page.dart` | 실제 예약번호·매니저·결제 기록. 다른 회원 예약은 표시하지 않음 |
| 팀 목록·개설·상세 | `lib/view/team/` | `/team/select`, `/team/create`, `/team/apply`, `/team/leave`, `/team/delete`. 가입은 기존대로 즉시 처리 |
| 게시판 목록·상세·글쓰기 | `lib/view/board/` | `/board/...`, 댓글·대댓글. 공감·스크랩·HOT 집계는 없음 |
| 대여 경기로 매칭 글쓰기 | `lib/view/team_match/team_match_post_page.dart` | `/team_match/rentals/{c_id_seq}`, `POST /team_match/post`. 매칭신청 분류의 추가 버튼으로 진입 |
| 매칭 신청·수락·거절 | `lib/view/board/board_match_action.dart`, `board_match_card.dart` | `/team_match/request`, `/requests/{seq}`, `/accept`, `/reject` |
| 메시지 목록·채팅방 | `lib/view/chat/` | 별도 `/chat/token`, 방 생성·초대·나가기·종료, WebSocket. 그룹별 읽음·파일 전송·개인별 온라인 상태는 없음 |
| MY | `lib/view/account/account_page.dart` | 실제 로그인 정보·가입 종목과 지원 메뉴. 임의 점수·포인트를 표시하지 않음 |
| 공지 | `lib/view/announcement/announcement_page.dart` | 사용자 대상 `/announce`, 서버 분류·본문 |
| 1:1 문의 | `lib/view/inquiry/inquiry_page.dart` | `/inquiry/insert`, `/inquiry/list`. 기존 답변 이후 후속 답변·깊이 유지 |
| 경기 결과·상세 | `lib/view/result/result_page.dart` | `/match/result/customer/{id}`, `/match/result/{seq}`. 개인 기록만 제공, 상대팀 점수·전체 경기 통계 생성 안 함 |
| 제재·이의신청 | `lib/view/sanction/` | `/sanction/list`, `/appeal/list`, `/appeal/insert`. 실제 기한·상태·증빙 링크 사용 |

## 현재 서버로 구현할 수 없는 부분

- 구장 사진·원본 브랜드 로고: API 사진 필드·로컬 로고 에셋이 없어 공용 스포츠 마크와 안내 영역을 사용.
- 카카오·네이버·Apple 소셜 로그인, 아이디 중복 확인, SMS 인증: 해당 API 없음.
- 회원정보 조회·수정: 전용 API 없음. MY는 로그인 응답에서 확인할 수 있는 정보만 표시.
- 개인 알림·읽음 처리: API 없음. 공지 조회와 구분.
- 신고 작성·내역: Python 소스는 있으나 현재 `main.py`에서 report router가 등록되지 않음. 프론트에서 존재하지 않는 경로로 전송하지 않음.
- 레벨 추천·랭킹·상대팀 스코어·팀 전체 경기 통계: 현재 조회 응답만으로 계산할 근거가 부족함.
- 전체 팀원 명단은 지원하지 않습니다. 팀 가입 승인·거절은 2026-10-28 추가 기능과 아래 설명을 따릅니다.
- 실제 PG 결제·파일 업로드·증빙 업로드: 현재 API 범위 밖. 결제 기록 저장 및 증빙 공유 링크만 사용.

Python·실제 DB는 변경하지 않았습니다. 위 기능을 추가하려면 별도 백엔드 변경 승인이 필요합니다.

## 실행과 검증

```sh
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000
flutter test
flutter analyze
flutter build web --debug
```

Android 에뮬레이터는 `http://10.0.2.2:8000`, 실제 기기는 서버의 LAN 주소를 사용합니다.
테스트는 Mock HTTP·WebSocket을 사용하며 실제 DB에 쓰지 않습니다.
Mock 검증은 실제 서버·기기 검증과 구분합니다.

검증 결과: Mock·위젯 테스트 40개 통과, 변경 영역 정적 검사 통과.
전체 분석에는 기존 모델의 snake_case 명명 안내 39건이 남아 있으며 관련 없는 모델 이름은 변경하지 않았습니다.

## 팀장 위임 추가 (2026-10-28)

- 팀 목록 → 팀 정보 → 팀장 위임에서 같은 팀 팀원의 종목별 회원 아이디를 입력합니다.
- `POST /team/captain/{t_id}`에 `c_id_seq`, `new_captain`을 전달합니다. 현재 팀장·운영 중인 팀에만 버튼을 표시하고 최종 소속·권한 검증은 서버를 따릅니다.
- 팀원 목록 API가 없어 목록 선택은 제공하지 않습니다. 진행 중인 대여·연결 매칭 글 이전과 기존 결제자 유지 사항을 확인 후 제출합니다.
- 성공 시 팀·게시판·매칭·예약 캐시를 갱신합니다. 실패 시 입력 보존, 중복 제출 차단, 계정 전환 후 이전 응답 무시를 Mock으로 검증합니다.
- Python·DB 변경 및 실제 위임 요청은 실행하지 않았습니다.

## 팀원모집 승인 추가 (2026-10-28)

- 사용자 추가 컬럼 `t_register.tr_state`(VARCHAR(50), NOT NULL, 기본 빈 문자열)를 읽기 전용으로 확인했습니다. 새 테이블·컬럼·데이터를 실제 DB에 쓰지 않았습니다.
- 상태: `대기` → `승인`/`거절`, 탈퇴 시 `탈퇴`. 기존 빈 상태의 가입 기록은 호환합니다. `tr_date`는 최근 상태 변경 시각입니다. 신청 시 소속을 바꾸지 않고 승인 시 `c_category=가입` 및 `customer.c_team`을 갱신합니다.
- `POST /team/apply/{t_id}`는 이제 즉시 가입이 아닌 승인 대기입니다. 선택적 `bulletin_seq`를 받으면 모집 글의 실제 소속 팀과 대상을 검증합니다. 기존 팀 화면의 가입도 대기로 처리합니다.
- `GET /team/recruitment/{bulletin_seq}?c_id_seq=...`는 실제 팀과 본인 상태를 반환하고 현재 팀장에게만 신청자 목록을 반환합니다. `POST /team/approve/{t_id}`, `/team/reject/{t_id}` 요청은 `c_id_seq`(팀장), `applicant_id`입니다.
- 모집 글이 없어도 팀 정보 화면에서 `GET /team/applications/{t_id}`로 현재 팀장이 신청 목록을 관리합니다.
- 모집 글 상세에 신청 버튼·대기 상태·재신청, 팀장에게 신청자 목록·승인·거절을 표시합니다. 같은 팀의 여러 모집 글은 신청 상태를 공유합니다. 별도 게시글 FK·처리자·변경 이력 컬럼이 없어 게시글별 신청 및 과거 승인 이력은 제공하지 않습니다.
- 승인 때 다른 팀 가입 여부를 재검증하고 다른 팀의 대기 신청을 거절 처리합니다. 대기·거절은 인원 집계·팀장 위임에서 제외합니다. 폐지된 팀의 대기 신청도 종료합니다.
- 서버를 재시작하여 새 라우터를 반영해야 합니다. 실제 가입·승인 API는 실행하지 않았으며 Mock 검증과 실제 연동 검증은 구분합니다.

## 목업 디자인 보완 (2026-10-28)

- 첨부된 전체 회원 화면을 기준으로 공통 제목·본문 크기, 흰 배경, 파란 주요 동작, 연한 윤곽선 카드와 상태 배지를 보완했습니다.
- MY는 가로 프로필과 실제 가입 종목, 활동/고객지원 메뉴로 구성합니다. 구장 상세는 API의 주소·인원·운영시간·매니저·이용료를 표시하고 예약/전체 대여 버튼을 하단에 고정합니다. 구장 사진 응답이 없어 중립적인 아이콘을 사용합니다.
- 예약 내역에는 실제 결제/취소 상태 배지를 표시하며 결제 번호·금액·취소 사유 및 기존 동작을 유지합니다. 팀 목록은 팀장 배지와 실제 팀 정보, 채팅은 실제 방 이름·참여 권한으로 구성합니다.
- 상대 점수·회원 레벨·읽지 않은 메시지 수·소셜 로그인·프로필 수정 등 API가 제공하지 않는 정보와 동작을 목업만 보고 추가하지 않았습니다. Python·DB는 이번 디자인 보완에서 수정하지 않았습니다.
- `test/member_design_test.dart`는 실제 앱 테마를 사용하여 320/390px·1.2배 글꼴·구장 전체 대여 이동과 MY/예약 내역 표시를 Mock으로 확인합니다. 미리보기는 `flutter test test/member_design_test.dart --dart-define=MEMBER_PREVIEW_PATH=/tmp/gongin_design_v2_20261028`로 생성할 수 있습니다. 실제 기기와 서버 연동은 별도 확인이 필요합니다.
