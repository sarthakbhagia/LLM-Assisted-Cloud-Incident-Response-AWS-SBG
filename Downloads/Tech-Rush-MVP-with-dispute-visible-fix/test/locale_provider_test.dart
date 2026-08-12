import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:kaamsetu/providers/locale_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('localeProvider defaults to English', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    final locale = container.read(localeProvider);
    expect(locale.languageCode, equals('en'));
  });

  test('setLocale changes locale and updates state', () async {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await container.read(localeProvider.notifier).setLocale(const Locale('hi'));
    expect(container.read(localeProvider).languageCode, equals('hi'));

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('selected_language_code'), equals('hi'));
  });

  test('toggleLocale switches between en and hi', () async {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    expect(container.read(localeProvider).languageCode, equals('en'));

    await container.read(localeProvider.notifier).toggleLocale();
    expect(container.read(localeProvider).languageCode, equals('hi'));

    await container.read(localeProvider.notifier).toggleLocale();
    expect(container.read(localeProvider).languageCode, equals('en'));
  });
}
