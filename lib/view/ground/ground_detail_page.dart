// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_features.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../reservation/reservation_page.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 실측 API 정보만 표시하며 전체 대여와 자리 예약을 하단 동작으로 구분합니다.
class GroundDetailPage extends ConsumerWidget {
  const GroundDetailPage({super.key, required this.code});
  final String code;
  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
    appBar: AppBar(title: const Text('구장 안내')),
    body: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 640),
        child: ApiContent(
          query: apiQuery('/ground/${Uri.encodeComponent(code)}'),
          builder: (ground) {
            void reserve(bool rental) => Navigator.push(
              context,
              MaterialPageRoute<void>(
                builder: (_) => ReservationPage(ground: ground, rental: rental),
              ),
            );
            return Column(
              children: [
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                    children: [
                      // 사진 응답이 없으므로 실제 구장 사진 대신 중립적인 구장 아이콘을 사용합니다.
                      Container(
                        height: 160,
                        margin: const EdgeInsets.only(bottom: 20),
                        decoration: BoxDecoration(
                          color: MemberStyle.surface,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: const Center(
                          child: Icon(
                            Icons.stadium_outlined,
                            size: 64,
                            color: MemberStyle.muted,
                          ),
                        ),
                      ),
                      const Row(
                        children: [
                          MemberStatusBadge('구장 안내', color: MemberStyle.green),
                          SizedBox(width: 6),
                          MemberStatusBadge('예약 시간 선택'),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        '${ground['g_name']}',
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '${ground['g_address']}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: MemberStyle.muted,
                        ),
                      ),
                      const SizedBox(height: 18),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: MemberMetricTile(
                              '수용 인원',
                              '${ground['g_num']}명',
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: MemberMetricTile('운영시간', ground['g_time']),
                          ),
                        ],
                      ),
                      const MemberSectionTitle('이용 안내'),
                      Text(
                        '${ground['g_information'] ?? '등록된 이용 안내가 없습니다.'}',
                        style: const TextStyle(height: 1.8),
                      ),
                      const SizedBox(height: 16),
                      const Divider(),
                      const MemberSectionTitle('오늘의 매니저'),
                      Row(
                        children: [
                          const CircleAvatar(
                            backgroundColor: MemberStyle.blue,
                            child: Icon(Icons.sports, color: Colors.white),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              '${ground['m_name'] ?? '배정 정보 없음'}',
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                DecoratedBox(
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    border: Border(top: BorderSide(color: MemberStyle.line)),
                  ),
                  child: SafeArea(
                    top: false,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Text(
                                '구장 이용료',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: MemberStyle.muted,
                                ),
                              ),
                              Text(
                                '${ground['g_price']}원',
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          FilledButton(
                            onPressed: () => reserve(false),
                            child: const Text('실력 매칭 · 자리 예약'),
                          ),
                          TextButton(
                            onPressed: () => reserve(true),
                            child: const Text('구장 전체 대여'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
