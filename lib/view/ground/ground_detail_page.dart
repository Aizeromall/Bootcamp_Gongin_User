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
// 실제 구장 상세·배정 매니저를 표시하고 자리 예약과 전체 대여를 구분합니다.
class GroundDetailPage extends ConsumerWidget {
  const GroundDetailPage({super.key, required this.code});
  final String code;
  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
    appBar: AppBar(title: const Text('구장 안내')),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        ApiContent(
          query: apiQuery('/ground/${Uri.encodeComponent(code)}'),
          builder: (ground) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                height: 160,
                decoration: BoxDecoration(
                  color: MemberStyle.greenSurface,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Icon(
                  Icons.stadium_outlined,
                  size: 80,
                  color: MemberStyle.green,
                ),
              ),
              const SizedBox(height: 22),
              Text(
                '${ground['g_name']}',
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                '${ground['g_address']}',
                style: const TextStyle(color: MemberStyle.muted),
              ),
              const SizedBox(height: 20),
              MemberPanel(
                child: Column(
                  children: [
                    MemberInfoRow('수용 인원', '${ground['g_num']}명'),
                    MemberInfoRow('운영시간', ground['g_time']),
                    MemberInfoRow('이용료', '${ground['g_price']}원'),
                    MemberInfoRow('오늘 매니저', ground['m_name'] ?? '배정 정보 없음'),
                  ],
                ),
              ),
              const Text(
                '이용 안내',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 10),
              Text(
                '${ground['g_information'] ?? ''}',
                style: const TextStyle(height: 1.8),
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => ReservationPage(ground: ground),
                  ),
                ),
                child: const Text('실력 매칭 · 자리 예약'),
              ),
              const SizedBox(height: 10),
              OutlinedButton(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        ReservationPage(ground: ground, rental: true),
                  ),
                ),
                child: const Text('구장 전체 대여'),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
