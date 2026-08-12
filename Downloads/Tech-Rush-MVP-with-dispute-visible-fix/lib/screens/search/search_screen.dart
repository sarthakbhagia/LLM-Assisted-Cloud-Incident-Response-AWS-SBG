import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/theme.dart';
import '../../core/spacing.dart';
import '../../models/job.dart';
import '../../providers/search_provider.dart';
import '../../providers/job_provider.dart';
import '../../widgets/service_card.dart';
import '../../widgets/skeleton_service_card.dart';
import '../../widgets/empty_state.dart';
import '../../l10n/app_localizations.dart';

class SearchScreen extends ConsumerStatefulWidget {
  final String initialQuery;
  const SearchScreen({super.key, this.initialQuery = ''});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  late final TextEditingController _controller;
  late final FocusNode _focusNode;
  Timer? _debounceTimer;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _query = widget.initialQuery;
    _controller = TextEditingController(text: _query);
    _focusNode = FocusNode();

    // Auto-focus field after build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        _focusNode.requestFocus();
      }
    });
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _onQueryChanged(String text) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 300), () {
      if (mounted) {
        setState(() {
          _query = text;
        });
      }
    });
  }

  void _submitSearch(String text) {
    if (text.trim().isNotEmpty) {
      ref.read(recentSearchesProvider.notifier).addSearch(text.trim());
      setState(() {
        _query = text.trim();
        _controller.text = _query;
        _controller.selection = TextSelection.fromPosition(
          TextPosition(offset: _query.length),
        );
      });
    }
  }

  void _clearSearch() {
    _debounceTimer?.cancel();
    _controller.clear();
    setState(() {
      _query = '';
    });
    _focusNode.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final recentSearches = ref.watch(recentSearchesProvider);
    final isQueryEmpty = _query.trim().isEmpty;

    return Scaffold(
      backgroundColor: AppColors.canvas,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: AppColors.inkPrimary),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/dashboard');
            }
          },
        ),
        titleSpacing: 0,
        title: Padding(
          padding: const EdgeInsets.only(right: 16),
          child: SizedBox(
            height: 44,
            child: TextField(
              controller: _controller,
              focusNode: _focusNode,
              onChanged: _onQueryChanged,
              onSubmitted: _submitSearch,
              style: GoogleFonts.inter(
                fontSize: 14,
                color: AppColors.inkPrimary,
                fontWeight: FontWeight.w500,
              ),
              decoration: InputDecoration(
                hintText: l10n.dashboardEmployerSearchPlaceholder,
                hintStyle: GoogleFonts.inter(
                  fontSize: 13,
                  color: AppColors.inkMuted,
                ),
                prefixIcon: const Icon(
                  Icons.search_rounded,
                  size: 20,
                  color: AppColors.brand,
                ),
                suffixIcon: _controller.text.isNotEmpty
                    ? GestureDetector(
                        onTap: _clearSearch,
                        child: const Icon(
                          Icons.cancel_rounded,
                          size: 18,
                          color: AppColors.inkMuted,
                        ),
                      )
                    : null,
                contentPadding: const EdgeInsets.symmetric(vertical: 10),
                fillColor: AppColors.canvas,
                filled: true,
                border: OutlineInputBorder(
                  borderRadius: AppRadii.pill,
                  borderSide: const BorderSide(color: AppColors.border),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: AppRadii.pill,
                  borderSide: const BorderSide(color: AppColors.border),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: AppRadii.pill,
                  borderSide: const BorderSide(color: AppColors.brand, width: 1.5),
                ),
              ),
            ),
          ),
        ),
      ),
      body: isQueryEmpty
          ? _buildRecentSearches(recentSearches)
          : ref.watch(searchJobsProvider(_query)).when(
                data: (results) {
                  if (results.isEmpty) {
                    return _buildEmptyState();
                  }
                  return _buildResultsList(results);
                },
                loading: () => Padding(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: SkeletonList(count: 3),
                ),
                error: (err, stack) => _buildEmptyState(),
              ),
    );
  }

  Widget _buildRecentSearches(List<String> recentSearches) {
    if (recentSearches.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off_rounded, size: 56, color: AppColors.inkMuted.withValues(alpha: 0.5)),
            const SizedBox(height: 12),
            Text(
              'Search for any daily wage service or job title',
              style: GoogleFonts.inter(
                fontSize: 14,
                color: AppColors.inkMuted,
              ),
            ),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Recent Searches',
                style: GoogleFonts.sora(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: AppColors.inkPrimary,
                ),
              ),
              GestureDetector(
                onTap: () {
                  ref.read(recentSearchesProvider.notifier).clearAll();
                },
                child: Text(
                  'Clear History',
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppColors.brand,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: recentSearches.map((search) {
              return InputChip(
                label: Text(
                  search,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    color: AppColors.inkPrimary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                backgroundColor: AppColors.surface,
                elevation: 0,
                shadowColor: Colors.transparent,
                shape: RoundedRectangleBorder(
                  borderRadius: AppRadii.pill,
                  side: const BorderSide(color: AppColors.border),
                ),
                avatar: const Icon(
                  Icons.history_rounded,
                  size: 16,
                  color: AppColors.inkMuted,
                ),
                onDeleted: () {
                  ref.read(recentSearchesProvider.notifier).removeSearch(search);
                },
                deleteIconColor: AppColors.inkMuted,
                onPressed: () {
                  _controller.text = search;
                  _submitSearch(search);
                },
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppColors.surface,
                shape: BoxShape.circle,
                border: Border.all(color: AppColors.border),
              ),
              child: const Icon(
                Icons.search_off_rounded,
                size: 44,
                color: AppColors.inkMuted,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              'No results for "$_query"',
              style: GoogleFonts.sora(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppColors.inkPrimary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 6),
            Text(
              'Try searching for "Painting", "Plumbing", "Cleaning" or a specific job keyword.',
              style: GoogleFonts.inter(
                fontSize: 13,
                color: AppColors.inkMuted,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.lg),
            ElevatedButton.icon(
              onPressed: _clearSearch,
              icon: const Icon(Icons.close_rounded, size: 16),
              label: const Text('Clear Search'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.brand,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: AppRadii.pill,
                ),
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultsList(List<Job> results) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Text(
            '${results.length} ${results.length == 1 ? "result" : "results"} found for "$_query"',
            style: GoogleFonts.spaceMono(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              color: AppColors.inkMuted,
            ),
          ),
        ),
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            itemCount: results.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final job = results[index];
              return ServiceCard(
                image: job.imageUrl,
                title: job.title,
                category: job.category,
                thumbsUpCount: null,
                thumbsUpPercentage: null,
                price: job.wage,
                originalPrice: job.originalWage,
                verified: job.verified,
                onSelect: () {
                  _submitSearch(_query);
                  context.push('/job/${job.id}');
                },
              );
            },
          ),
        ),
      ],
    );
  }
}
