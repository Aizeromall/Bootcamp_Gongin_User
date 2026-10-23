// ###  2026.10.23 구장 조회 Riverpod 상태관리 구성   - 신현진
//
// [이 파일의 역할]
// 화면(View)과 서버(FastAPI) 사이에서 구장(Ground) 데이터를 가져오고 상태를 보관하는 ViewModel
//   View  : ref.watch(...)로 상태를 구독 → 데이터가 바뀌면 화면이 자동으로 다시 그려짐
//   VM    : 이 파일. 서버 호출 + 상태(로딩/데이터/에러) 관리
//   Model : lib/model/ground_model.dart (JSON ↔ Ground 객체 변환)
//
// [연결된 서버 API] (python/FastAPI/match/ground_search.py)
//   GET /match/ground                 전체 구장 목록 (?keyword= 로 구장명/주소 검색)
//   GET /match/ground/{g_code}        구장 1건 상세
//
// [화면에서 사용하는 방법]
//   1) 목록 화면
//      final groundsAsync = ref.watch(groundListProvider);
//      groundsAsync.when(
//        data: (grounds) => ListView(...),                 // 조회 성공
//        loading: () => CircularProgressIndicator(),       // 조회 중
//        error: (error, stack) => Text('$error'),          // 조회 실패
//      );
//   2) 검색 버튼
//      ref.read(groundListProvider.notifier).searchGrounds('영등포');
//   3) 상세 화면
//      final groundAsync = ref.watch(groundDetailProvider('1'));

import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../model/ground_model.dart';

// FastAPI 서버 주소
// - Android 에뮬레이터에서 내 PC 서버에 접속할 때는 127.0.0.1 대신 10.0.2.2 사용
// - 실제 휴대폰으로 테스트할 때는 서버 PC의 IP(예: http://192.168.x.x:8000)로 변경
const String baseUrl = 'http://127.0.0.1:8000';

// ------------------------------------------------------------
// 구장 목록 상태관리 (목록 조회 + 검색)
// ------------------------------------------------------------

// AsyncNotifier<List<Ground>> : 상태가 "List<Ground>"이고, 서버 호출처럼 비동기로 채워지는 Notifier
// state는 AsyncValue로 감싸져 있어서 로딩(AsyncLoading) / 성공(AsyncData) / 실패(AsyncError)를 한 번에 표현
class GroundListNotifier extends AsyncNotifier<List<Ground>> {
  // 현재 검색어 (새로고침할 때 같은 검색 조건을 유지하기 위해 보관)
  String _keyword = '';

  // build() : Provider를 처음 사용하는 순간(ref.watch) 자동으로 1번 실행되는 초기값 함수
  // 여기서 반환한 값이 첫 state가 됨 → 화면에 들어오면 전체 구장 목록이 바로 조회됨
  @override
  Future<List<Ground>> build() async {
    return _fetchGrounds(_keyword);
  }

  // 서버에서 구장 목록을 받아 Ground 객체 목록으로 변환
  // keyword가 비어 있으면 전체 목록, 있으면 구장명/주소 검색 결과
  Future<List<Ground>> _fetchGrounds(String keyword) async {
    // Uri.parse(...).replace(queryParameters:) : 한글 검색어도 주소에 맞게 자동 인코딩
    final uri = Uri.parse('$baseUrl/match/ground').replace(
      queryParameters: keyword.isEmpty ? null : {'keyword': keyword},
    );
    final response = await http.get(uri);

    // 200이 아니면 서버 오류 → 예외를 던지면 state가 AsyncError가 되어 화면의 error: 부분이 표시됨
    if (response.statusCode != 200) {
      throw Exception('구장 목록 조회 실패 (${response.statusCode})');
    }

    // utf8.decode(bodyBytes) : response.body를 그대로 쓰면 한글이 깨질 수 있어서 바이트를 UTF-8로 직접 변환
    final data = json.decode(utf8.decode(response.bodyBytes));
    // 서버 응답 형식 : {"results": [ {구장1}, {구장2}, ... ]}
    final List results = data['results'];
    // JSON 1개(Map)씩 Ground.fromJson으로 바꿔서 List<Ground>로 만듦
    return results.map((item) => Ground.fromJson(item)).toList();
  }

  // 구장 검색 (검색 버튼 / 검색창 입력 완료 시 호출)
  // 빈 문자열을 넣으면 전체 목록으로 돌아감
  Future<void> searchGrounds(String keyword) async {
    _keyword = keyword.trim();  // 앞뒤 공백 제거
    // 1) 먼저 로딩 상태로 바꿔서 화면에 로딩 표시
    state = const AsyncLoading();
    // 2) AsyncValue.guard : 안의 함수가 성공하면 AsyncData, 예외가 나면 AsyncError로 자동 변환
    //    (try-catch를 직접 쓰지 않아도 에러가 state에 담김)
    state = await AsyncValue.guard(() => _fetchGrounds(_keyword));
  }

  // 새로고침 (당겨서 새로고침 / 예약 후 목록 갱신 시 호출)
  // 현재 검색어를 그대로 유지한 채 다시 조회
  Future<void> refreshGrounds() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => _fetchGrounds(_keyword));
  }
}

// 화면에서 구장 목록 상태에 접근하는 Provider
//   ref.watch(groundListProvider)           → 상태(AsyncValue<List<Ground>>) 구독
//   ref.read(groundListProvider.notifier)   → GroundListNotifier의 함수(search/refresh) 호출
// GroundListNotifier.new : Provider가 처음 쓰일 때 Notifier 객체를 만드는 생성자
final groundListProvider =
    AsyncNotifierProvider<GroundListNotifier, List<Ground>>(GroundListNotifier.new);

// ------------------------------------------------------------
// 구장 1건 상세 조회
// ------------------------------------------------------------

// FutureProvider.family : 매개변수(g_code)를 받아서 비동기로 값을 1번 가져오는 Provider
// 상세 화면은 조회만 하고 바꿀 상태가 없어서 Notifier 대신 FutureProvider 사용
// g_code가 같으면 결과를 재사용하고, 다르면 구장별로 따로 조회
// 사용 예: ref.watch(groundDetailProvider(ground.g_code))
final groundDetailProvider = FutureProvider.family<Ground, String>((ref, gCode) async {
  final response = await http.get(Uri.parse('$baseUrl/match/ground/$gCode'));

  // 404 : 존재하지 않는 구장 코드 (서버에서 detail 메시지를 보내줌)
  if (response.statusCode == 404) {
    throw Exception('존재하지 않는 구장입니다.');
  }
  if (response.statusCode != 200) {
    throw Exception('구장 상세 조회 실패 (${response.statusCode})');
  }

  // 상세 응답은 목록과 달리 {"results": ...} 없이 구장 1개 JSON이 바로 옴
  final data = json.decode(utf8.decode(response.bodyBytes));
  return Ground.fromJson(data);
});
