// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../service/member_api.dart';
import '../../vm/banner_state.dart';

class HomeBanner extends ConsumerStatefulWidget {
  const HomeBanner({super.key});

  @override
  ConsumerState<HomeBanner> createState() => _HomeBannerState();
}

class _HomeBannerState extends ConsumerState<HomeBanner>
    with WidgetsBindingObserver {
  Timer? timer;
  int index = 0;
  bool refreshing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // 4초마다 서버의 공개 목록도 다시 확인하여 비활성화된 배너를 제외합니다.
    timer = Timer.periodic(const Duration(seconds: 4), (_) async {
      final state = WidgetsBinding.instance.lifecycleState;
      if (state != null && state != AppLifecycleState.resumed) return;
      if (!mounted || refreshing) return;
      refreshing = true;
      try {
        final ids = await ref.refresh(bannerProvider.future);
        if (mounted && ids.isNotEmpty) setState(() => index++);
      } catch (_) {
        // 오류는 provider 상태의 재시도 안내로 표시합니다.
      } finally {
        refreshing = false;
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) ref.invalidate(bannerProvider);
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final banners = ref.watch(bannerProvider);
    return ClipRRect(
      borderRadius: BorderRadius.circular(19),
      child: SizedBox(
        height: 145,
        child: banners.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (_, _) => Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('배너를 불러오지 못했습니다.'),
                TextButton(
                  onPressed: () => ref.invalidate(bannerProvider),
                  child: const Text('다시 시도'),
                ),
              ],
            ),
          ),
          data: (ids) {
            if (ids.isEmpty) {
              return const Center(child: Text('진행 중인 배너가 없습니다.'));
            }
            final id = ids[index % ids.length];
            return GestureDetector(
              onHorizontalDragEnd: ids.length < 2
                  ? null
                  : (details) {
                      final velocity = details.primaryVelocity ?? 0;
                      if (velocity == 0) return;
                      setState(
                        () => index =
                            (index + (velocity < 0 ? 1 : -1)) % ids.length,
                      );
                    },
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 250),
                child: Image.network(
                  '${MemberApi.baseUrl}/banner/$id/image',
                  key: ValueKey('home-banner-$id'),
                  width: double.infinity,
                  height: 145,
                  fit: BoxFit.cover,
                  errorBuilder: (context, _, _) => ColoredBox(
                    color: Theme.of(context).colorScheme.surfaceContainerHigh,
                    child: const Center(child: Text('배너 이미지를 불러오지 못했습니다.')),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (배너 수동 넘김)
