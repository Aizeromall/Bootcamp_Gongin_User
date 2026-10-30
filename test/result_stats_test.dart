// 작업자 : 최현준
// 최초 작업 일 : 2026-10-30
import 'package:bootcamp_project_gongin_admin_app/view/result/result_page.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('확인된 스탯을 한글로 변환하고 미확인 형식은 추측하지 않는다', () {
    expect(resultStats('G:1,A:0,S:2,F:3,M:4,E:5,Y:0,R:1'), {
      '골': '1',
      '어시스트': '0',
      '슈팅': '2',
      '파울': '3',
      '찬스 미스': '4',
      '실책': '5',
      '경고': '0',
      '퇴장': '1',
    });
    expect(resultStats('100'), isNull);
    expect(resultStats('G:1,X:2'), isNull);
    expect(resultStats('G:1,G:2'), isNull);
    expect(resultStats(null), isNull);
    expect(resultStats('P:20,T:3,A:4,RB:7,F:2,TO:1', sport: 'BASKETBALL'), {
      '득점': '20',
      '3점슛 성공': '3',
      '어시스트': '4',
      '리바운드': '7',
      '파울': '2',
      '턴오버': '1',
    });
    expect(
      resultStats('P:4,B:2,SA:1,F:0,E:3', sport: 'VOLLEYBALL')?['E'],
      isNull,
    );
    expect(
      resultStats('P:4,B:2,SA:1,F:0,E:3', sport: 'VOLLEYBALL')?['범실'],
      '3',
    );
    expect(
      resultStats(
        'H:2,HR:1,RBI:3,RS:1,BB:2,O:2,K:1,E:0',
        sport: 'BASEBALL',
      )?['홈런'],
      '1',
    );
    expect(resultStats('P:4', sport: 'UNKNOWN'), isNull);
  });
  test('본인 이름이 일치하는 부상의 위치와 사유만 선택한다', () {
    const raw =
        '[{"name":"홍길동","body_parts":["무릎","발목"],"description":"충돌","severity":"기타 정보"},'
        '{"name":"다른회원","body_parts":["머리"],"description":"넘어짐"}]';
    final result = ownInjuries(raw, '홍길동');
    expect(result.length, 1);
    expect(result.first.parts, '무릎, 발목');
    expect(result.first.reason, '충돌');
    expect(ownInjuries(raw, '다른 사람'), isEmpty);
    expect(ownInjuries('이전 텍스트', '홍길동'), isEmpty);
    expect(ownInjuries(raw, ''), isEmpty);
  });
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
