import 'package:flutter_riverpod/flutter_riverpod.dart';

class JobFilterState {
  final Set<String> categories;
  final double minPrice;
  final double maxPrice;
  final String sortBy; // 'most_recent', 'price_low', 'price_high', 'rating', 'urgency'

  const JobFilterState({
    this.categories = const {},
    this.minPrice = 500.0,
    this.maxPrice = 10000.0,
    this.sortBy = 'most_recent',
  });

  bool get isActive =>
      categories.isNotEmpty ||
      minPrice > 500.0 ||
      maxPrice < 10000.0 ||
      sortBy != 'most_recent';

  int get activeCount {
    int count = 0;
    if (categories.isNotEmpty) count += categories.length;
    if (minPrice > 500.0 || maxPrice < 3000.0) count++;
    if (sortBy != 'most_recent') count++;
    return count;
  }

  JobFilterState copyWith({
    Set<String>? categories,
    double? minPrice,
    double? maxPrice,
    String? sortBy,
  }) {
    return JobFilterState(
      categories: categories ?? this.categories,
      minPrice: minPrice ?? this.minPrice,
      maxPrice: maxPrice ?? this.maxPrice,
      sortBy: sortBy ?? this.sortBy,
    );
  }
}

class FilterNotifier extends StateNotifier<JobFilterState> {
  FilterNotifier() : super(const JobFilterState());

  void setCategories(Set<String> categories) {
    state = state.copyWith(categories: categories);
  }

  void toggleCategory(String category) {
    final updated = Set<String>.from(state.categories);
    if (updated.contains(category)) {
      updated.remove(category);
    } else {
      updated.add(category);
    }
    state = state.copyWith(categories: updated);
  }

  void setPriceRange(double min, double max) {
    state = state.copyWith(minPrice: min, maxPrice: max);
  }

  void setSortBy(String sortBy) {
    state = state.copyWith(sortBy: sortBy);
  }

  void reset() {
    state = const JobFilterState();
  }
}

final jobFilterProvider =
    StateNotifierProvider<FilterNotifier, JobFilterState>((ref) {
  return FilterNotifier();
});
