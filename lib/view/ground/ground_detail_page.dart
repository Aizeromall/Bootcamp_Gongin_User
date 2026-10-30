// 2026-10-28
// 작업자 : 양태건
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../service/member_api.dart';
import '../../vm/member_features.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../shared/ground_price.dart';
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
            final individualPrice = individualGroundPrice(
              ground['g_price'],
              ground['g_num'],
            );
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
                      // 수정 일 : 2026-10-30 / 작업자 : 최현준
                      // 해당 구장의 사진 목록과 원본 이미지를 조회합니다.
                      _GroundPhotos(code: code),
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
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    border: const Border(
                      top: BorderSide(color: MemberStyle.line),
                    ),
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
                                '1인 예상 이용료',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: MemberStyle.muted,
                                ),
                              ),
                              Text(
                                individualPrice == null
                                    ? '확인 불가'
                                    : '$individualPrice원',
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          // 수정 일 : 2026-10-30 / 작업자 : 최현준
                          // 전체 구장 대여는 인원으로 나누지 않은 금액입니다.
                          Text(
                            '전체 대여 ${ground['g_price'] == null ? '금액 확인 불가' : "${ground['g_price']}원"}',
                            textAlign: TextAlign.end,
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

class _GroundPhotos extends ConsumerWidget {
  const _GroundPhotos({required this.code});
  final String code;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = apiQuery('/ground/${Uri.encodeComponent(code)}/photos');
    Widget message(Widget child) => Center(child: child);
    return Container(
      height: 180,
      margin: const EdgeInsets.only(bottom: 20),
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(16),
      ),
      child: ref
          .watch(apiDocumentProvider(query))
          .when(
            loading: () => message(const CircularProgressIndicator()),
            error: (_, _) => message(
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('구장 사진을 불러오지 못했습니다.'),
                  TextButton(
                    onPressed: () => ref.invalidate(apiDocumentProvider(query)),
                    child: const Text('다시 시도'),
                  ),
                ],
              ),
            ),
            data: (data) {
              final rows = data['results'];
              if (rows is! List ||
                  rows.any(
                    (row) =>
                        row is! Map ||
                        row['shoot_seq'] is! int ||
                        (row['shoot_seq'] as int) <= 0,
                  )) {
                return message(const Text('구장 사진 정보를 확인할 수 없습니다.'));
              }
              if (rows.isEmpty) return message(const Text('등록된 구장 사진이 없습니다.'));
              final ids = [
                for (final row in rows) (row as Map)['shoot_seq'] as int,
              ];
              return _PhotoCarousel(
                key: ValueKey('$code-${ids.join(',')}'),
                code: code,
                ids: ids,
              );
            },
          ),
    );
  }
}

// 수정 일 : 2026-10-30 / 작업자 : 최현준
// 수동 드래그가 끝나면 3초를 다시 세고, 마지막 사진 뒤에는 처음으로 돌아갑니다.
class _PhotoCarousel extends StatefulWidget {
  const _PhotoCarousel({super.key, required this.code, required this.ids});
  final String code;
  final List<int> ids;
  @override
  State<_PhotoCarousel> createState() => _PhotoCarouselState();
}

class _PhotoCarouselState extends State<_PhotoCarousel> {
  final controller = PageController();
  Timer? timer;
  bool dragging = false;
  int index = 0;

  @override
  void initState() {
    super.initState();
    startTimer();
  }

  void startTimer() {
    timer?.cancel();
    if (widget.ids.length < 2) return;
    timer = Timer.periodic(const Duration(seconds: 3), (_) {
      final lifecycle = WidgetsBinding.instance.lifecycleState;
      if (!mounted ||
          !controller.hasClients ||
          dragging ||
          (lifecycle != null && lifecycle != AppLifecycleState.resumed) ||
          ModalRoute.of(context)?.isCurrent == false) {
        return;
      }
      if (index >= widget.ids.length - 1) {
        controller.jumpToPage(0);
      } else {
        controller.animateToPage(
          index + 1,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
        );
      }
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(
    BuildContext context,
  ) => NotificationListener<ScrollNotification>(
    onNotification: (event) {
      if (event.depth == 0 &&
          event is ScrollStartNotification &&
          event.dragDetails != null) {
        dragging = true;
        timer?.cancel();
      } else if (event.depth == 0 &&
          event is ScrollEndNotification &&
          dragging) {
        dragging = false;
        startTimer();
      }
      return false;
    },
    child: PageView.builder(
      controller: controller,
      itemCount: widget.ids.length,
      onPageChanged: (value) => index = value,
      itemBuilder: (context, index) {
        final id = widget.ids[index];
        return Image.network(
          '${MemberApi.baseUrl}/ground/${Uri.encodeComponent(widget.code)}/photos/$id',
          key: ValueKey('ground-photo-$id'),
          width: double.infinity,
          fit: BoxFit.cover,
          loadingBuilder: (context, child, progress) => progress == null
              ? child
              : const Center(child: CircularProgressIndicator()),
          errorBuilder: (context, _, _) =>
              const Center(child: Text('사진을 불러오지 못했습니다.')),
        );
      },
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (테마 대비 적용)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (구장 사진 연결)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (구장 사진 자동 넘김)
