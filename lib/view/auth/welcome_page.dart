// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';

import '../shared/member_components.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
class WelcomePage extends StatelessWidget {
  const WelcomePage({super.key, required this.onStart});
  final VoidCallback onStart;
  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            const Spacer(),
            const MemberBrand(large: true),
            const SizedBox(height: 14),
            const Text(
              '축구 · 배구 · 농구 · 야구',
              style: TextStyle(color: Colors.grey, fontSize: 13),
            ),
            const SizedBox(height: 8),
            const Text(
              '함께 뛰는 오늘, 더 즐거운 경기',
              style: TextStyle(color: Colors.grey),
            ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF172541),
                ),
                onPressed: onStart,
                child: const Text('시작하기'),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
