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
class CaptainTransfer extends Notifier<bool> {
  CaptainTransfer(this.key);
  final CaptainKey key;
  @override
  bool build() => false;

  Future<bool> submit(String newCaptain) async {
    if (state) return false;
    final session = ref.read(sessionProvider);
    if (session == null || ref.read(memberIdProvider) != key.memberId) {
      throw StateError('회원 정보를 다시 확인해 주세요.');
    }
    state = true;
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
        return false;
      }
      ref.invalidate(apiDocumentProvider);
      ref.invalidate(historyProvider);
      ref.invalidate(boardMatchInfoProvider);
      return true;
    } finally {
      if (ref.mounted) state = false;
    }
  }
}

final captainTransferProvider = NotifierProvider.autoDispose
    .family<CaptainTransfer, bool, CaptainKey>(CaptainTransfer.new);
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 모집 글의 신청·승인·거절을 회원별로 분리하고 서버 성공 후에만 관련 조회를 갱신합니다.
typedef RecruitmentKey = ({int seq, String id, int? teamId});

class RecruitmentAction extends Notifier<bool> {
  RecruitmentAction(this.key);
  final RecruitmentKey key;
  @override
  bool build() => false;
  Future<bool> submit(int teamId, String action, {String? applicant}) async {
    if (state) return false;
    final session = ref.read(sessionProvider);
    if (session == null) return false;
    state = true;
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
        return false;
      }
      ref.invalidate(teamDataRefreshProvider);
      return true;
    } finally {
      if (ref.mounted) state = false;
    }
  }
}

final recruitmentActionProvider = NotifierProvider.autoDispose
    .family<RecruitmentAction, bool, RecruitmentKey>(RecruitmentAction.new);
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
