import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const String _languagePreferenceKey = 'selected_language_code';

class LocaleNotifier extends StateNotifier<Locale> {
  LocaleNotifier() : super(const Locale('en')) {
    _loadSavedLocale();
  }

  Future<void> _loadSavedLocale() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedCode = prefs.getString(_languagePreferenceKey);
      if (savedCode != null && (savedCode == 'en' || savedCode == 'hi')) {
        state = Locale(savedCode);
      }
    } catch (_) {
      // Fallback to default Locale('en') if error reading preferences
    }
  }

  Future<void> setLocale(Locale newLocale) async {
    if (newLocale.languageCode != 'en' && newLocale.languageCode != 'hi') return;
    if (state == newLocale) return;

    state = newLocale;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_languagePreferenceKey, newLocale.languageCode);
    } catch (_) {}
  }

  Future<void> toggleLocale() async {
    final nextCode = state.languageCode == 'en' ? 'hi' : 'en';
    await setLocale(Locale(nextCode));
  }
}

final localeProvider = StateNotifierProvider<LocaleNotifier, Locale>((ref) {
  return LocaleNotifier();
});
