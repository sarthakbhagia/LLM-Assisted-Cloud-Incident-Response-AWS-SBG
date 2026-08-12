import 'package:flutter_riverpod/flutter_riverpod.dart';

class RecentSearchesNotifier extends StateNotifier<List<String>> {
  RecentSearchesNotifier()
      : super(['Painting', 'Plumbing', 'Deep Cleaning', 'Cooking', 'Electrical']);

  void addSearch(String query) {
    final trimmed = query.trim();
    if (trimmed.isEmpty) return;
    final updated = List<String>.from(state);
    updated.removeWhere((item) => item.toLowerCase() == trimmed.toLowerCase());
    updated.insert(0, trimmed);
    if (updated.length > 5) {
      state = updated.sublist(0, 5);
    } else {
      state = updated;
    }
  }

  void removeSearch(String query) {
    state = state.where((item) => item != query).toList();
  }

  void clearAll() {
    state = [];
  }
}

final recentSearchesProvider =
    StateNotifierProvider<RecentSearchesNotifier, List<String>>((ref) {
  return RecentSearchesNotifier();
});
