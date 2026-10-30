// 2026-10-28
// 작업자 : 양태건
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'board_state.dart';
import 'history_state.dart';
import 'member_features.dart';
import 'member_state.dart';

typedef CaptainKey = ({int teamId, String memberId});

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 팀·회원별 중복 위임을 차단하고 서버 성공 후 이전되는 예약·게시글까지 갱신합니다.
// 수정 일 : 2026-10-31 / 작업자 : 신현진
// 상태관리 방식 변경: Notifier<bool> → AsyncNotifier<void>
// 처리 중 여부는 state.isLoading, 요청 중 AsyncLoading → 성공 AsyncData / 실패 AsyncError (예외는 화면으로 다시 전달)
class CaptainTransfer extends AsyncNotifier<void> {
  CaptainTransfer(this.key);
  final CaptainKey key;
  @override
  void build() {}

  Future<bool> submit(String newCaptain) async {
    if (state.isLoading) return false;
    final session = ref.read(sessionProvider);
    if (session == null || ref.read(memberIdProvider) != key.memberId) {
      throw StateError('회원 정보를 다시 확인해 주세요.');
    }
    state = const AsyncLoading();
    try {
      await ref
          .read(memberApiProvider)
          .request(
            '/team/captain/${key.teamId}',
            method: 'POST',
            body: {'c_id_seq': key.memberId, 'new_captain': newCaptain.trim()},
          );
      if (!ref.mounted ||
          !identical(session, ref.read(sessionProvider)) ||
          ref.read(memberIdProvider) != key.memberId) {
        if (ref.mounted) state = const AsyncData(null);
        return false;
      }
      ref.invalidate(apiDocumentProvider);
      ref.invalidate(historyProvider);
      ref.invalidate(boardMatchInfoProvider);
      if (ref.mounted) state = const AsyncData(null);
      return true;
    } catch (error, stackTrace) {
      if (ref.mounted) state = AsyncError(error, stackTrace);
      rethrow;
    }
  }
}

final captainTransferProvider = AsyncNotifierProvider.autoDispose
    .family<CaptainTransfer, void, CaptainKey>(CaptainTransfer.new);
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 모집 글의 신청·승인·거절을 회원별로 분리하고 서버 성공 후에만 관련 조회를 갱신합니다.
typedef RecruitmentKey = ({int seq, String id, int? teamId});

// 수정 일 : 2026-10-31 / 작업자 : 신현진
// 상태관리 방식 변경: Notifier<bool> → AsyncNotifier<void> (처리 중 여부는 state.isLoading)
class RecruitmentAction extends AsyncNotifier<void> {
  RecruitmentAction(this.key);
  final RecruitmentKey key;
  @override
  void build() {}
  Future<bool> submit(int teamId, String action, {String? applicant}) async {
    if (state.isLoading) return false;
    final session = ref.read(sessionProvider);
    if (session == null) return false;
    state = const AsyncLoading();
    try {
      await ref
          .read(memberApiProvider)
          .request(
            '/team/$action/$teamId',
            method: 'POST',
            body: {
              'c_id_seq': key.id,
              if (action == 'apply') 'bulletin_seq': key.seq,
              'applicant_id': ?applicant,
            },
          );
      if (!ref.mounted || !identical(session, ref.read(sessionProvider))) {
        if (ref.mounted) state = const AsyncData(null);
        return false;
      }
      ref.invalidate(teamDataRefreshProvider);
      if (ref.mounted) state = const AsyncData(null);
      return true;
    } catch (error, stackTrace) {
      if (ref.mounted) state = AsyncError(error, stackTrace);
      rethrow;
    }
  }
}

final recruitmentActionProvider = AsyncNotifierProvider.autoDispose
    .family<RecruitmentAction, void, RecruitmentKey>(RecruitmentAction.new);
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-31 / 작업자 : 신현진 (동작 Notifier AsyncNotifier<void> 변환)
