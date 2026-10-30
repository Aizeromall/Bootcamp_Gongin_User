// 2026-10-28
// 작업자 : 양태건
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../shared/ui.dart';

// 수정 일 : 2026-10-30 / 작업자 : 최현준
// 관리자 기록의 G:1,A:0 형식만 해석하고 미확인 형식은 수치를 추측하지 않습니다.
Map<String, String>? resultStats(Object? value, {Object? sport = 'SOCCER'}) {
  if (value == null || '$value'.trim().isEmpty || value == '_') return null;
  const soccer = {
    'G': '골',
    'A': '어시스트',
    'S': '슈팅',
    'F': '파울',
    'M': '찬스 미스',
    'E': '실책',
    'Y': '경고',
    'R': '퇴장',
  };
  const basketball = {
    'P': '득점',
    'T': '3점슛 성공',
    'A': '어시스트',
    'RB': '리바운드',
    'F': '파울',
    'TO': '턴오버',
  };
  const volleyball = {
    'P': '공격 득점',
    'B': '블로킹',
    'SA': '서브에이스',
    'F': '파울',
    'E': '범실',
  };
  const baseball = {
    'H': '안타',
    'HR': '홈런',
    'RBI': '타점',
    'RS': '득점·홈인',
    'BB': '볼넷',
    'O': '아웃',
    'K': '삼진',
    'E': '실책',
  };
  final labels = switch ('$sport'.toUpperCase()) {
    'SOCCER' || '1' || '01' => soccer,
    'BASKETBALL' || '2' || '02' => basketball,
    'BASEBALL' || '3' || '03' => baseball,
    'VOLLEYBALL' || '4' || '04' => volleyball,
    _ => null,
  };
  if (labels == null) return null;
  final result = <String, String>{};
  for (final part in '$value'.split(',')) {
    final match = RegExp(r'^\s*([A-Za-z]+)\s*:\s*(\d+)\s*$').firstMatch(part);
    if (match == null) return null;
    final label = labels[match.group(1)!.toUpperCase()];
    if (label == null || result.containsKey(label)) return null;
    result[label] = match.group(2)!;
  }
  return result;
}

// 수정 일 : 2026-10-30 / 작업자 : 최현준
// 이름이 본인과 일치하는 부상 항목의 부위와 설명만 표시합니다.
List<({String parts, String reason})> ownInjuries(Object? raw, String name) {
  if (raw == null || name.trim().isEmpty) return [];
  Object? decoded = raw;
  if (raw is String) {
    try {
      decoded = jsonDecode(raw);
    } on FormatException {
      return [];
    }
  }
  if (decoded is! List) return [];
  final items = <({String parts, String reason})>[];
  for (final entry in decoded) {
    if (entry is! Map ||
        entry['name'] is! String ||
        (entry['name'] as String).trim() != name.trim()) {
      continue;
    }
    final parts = entry['body_parts'];
    final reason = entry['description'];
    if (parts is! List || reason is! String || reason.trim().isEmpty) continue;
    final names = parts
        .whereType<String>()
        .map((part) => part.trim())
        .where((part) => part.isNotEmpty)
        .toList();
    if (names.isEmpty) continue;
    items.add((parts: names.join(', '), reason: reason.trim()));
  }
  return items;
}

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 매니저가 기록한 회원 본인의 결과만 조회하며 상대 스코어·집계 통계를 만들지 않습니다.
class ResultPage extends ConsumerWidget {
  const ResultPage({super.key, this.seq});
  final int? seq;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // 수정 일 : 2026-10-30 / 작업자 : 김병재
    // 종목 Dropdown 제거: 목록은 모든 종목 회원 ID의 경기 결과를 합치고, 상세는 내 종목 ID 중 하나면 표시합니다.
    final ids = ref.watch(memberIdsProvider);
    final memberName = '${ref.watch(sessionProvider)?['c_name'] ?? ''}';
    return Scaffold(
      appBar: AppBar(title: const Text('경기 결과')),
      body: pageContent([
        ApiContent(
          allMembers: seq == null,
          query: apiQuery(
            seq == null ? '/match/result/customer/{id}' : '/match/result/$seq',
          ),
          builder: (data) {
            if (seq != null) {
              if (!ids.contains(data['c_id_seq'])) {
                return const Text('현재 회원의 경기 기록이 아닙니다.');
              }
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Container(
                    padding: const EdgeInsets.all(24),
                    margin: const EdgeInsets.only(bottom: 22),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF172541), Color(0xFF253D66)],
                      ),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Column(
                      children: [
                        Text(
                          '${data['g_name']}',
                          style: const TextStyle(color: Colors.white),
                        ),
                        const SizedBox(height: 16),
                        const Text(
                          '나의 경기 점수',
                          style: TextStyle(color: Colors.white70, fontSize: 12),
                        ),
                        Text(
                          '${data['c_r_r_score'] ?? '미기록'}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 40,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        Text(
                          '${data['c_r_r_team'] ?? ''}',
                          style: const TextStyle(color: Colors.white70),
                        ),
                      ],
                    ),
                  ),
                  MemberPanel(
                    child: Column(
                      children: [
                        MemberInfoRow('기록일', data['c_r_r_date']),
                        MemberInfoRow('경기 코드', data['c_r_r_code']),
                        MemberInfoRow('구장', data['g_name']),
                        MemberInfoRow('주소', data['g_address']),
                        MemberInfoRow('매니저', data['m_name']),
                        MemberInfoRow(
                          '출석',
                          data['c_r_r_attendance'] == null
                              ? '미기록'
                              : data['c_r_r_attendance'] == true
                              ? '출석'
                              : '결석',
                        ),
                        for (final injury in ownInjuries(
                          data['c_r_r_injury'],
                          memberName,
                        )) ...[
                          MemberInfoRow('부상 위치', injury.parts),
                          MemberInfoRow('부상 사유', injury.reason),
                        ],
                        // 확인된 약어만 한글 항목으로 바꿔 표시합니다.
                        if (resultStats(
                              data['c_r_r_statcode'],
                              sport: data['e_code'],
                            )
                            case final stats?)
                          for (final entry in stats.entries)
                            MemberInfoRow(entry.key, entry.value)
                        else
                          const MemberInfoRow(
                            '경기 기록',
                            '기록이 없거나 형식을 확인할 수 없습니다.',
                          ),
                      ],
                    ),
                  ),
                ],
              );
            }
            return FeedItems(
              data: data,
              item: (row) => MemberPanel(
                color: Colors.white,
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    '${row['g_name']}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  subtitle: Text(
                    '${row['c_r_r_date']}\n${row['c_r_r_team'] ?? ''}',
                  ),
                  trailing: Text(
                    '${row['c_r_r_score'] ?? '미기록'}',
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      color: MemberStyle.blue,
                    ),
                  ),
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute<void>(
                      builder: (_) => ResultPage(seq: row['c_r_r_seq'] as int),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ]),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (전 종목 경기 결과 통합)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
