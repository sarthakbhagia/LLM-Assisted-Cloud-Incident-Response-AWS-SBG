import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:kaamsetu/core/utils/formatters.dart';
import 'package:kaamsetu/l10n/app_localizations.dart';
import 'package:kaamsetu/providers/locale_provider.dart';
import 'package:kaamsetu/providers/user_provider.dart';
import 'package:kaamsetu/services/supabase_service.dart';
import 'package:kaamsetu/widgets/otp_verification_bottom_sheet.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  GoogleFonts.config.allowRuntimeFetching = false;

  setUpAll(() async {
    SharedPreferences.setMockInitialValues({});
    await SupabaseService.initialize();
  });

  group('OTP Verification Bugs & Security Unit Tests', () {
    test('Formatters.toWesternDigits converts Devanagari numerals to Western Arabic digits', () {
      expect(Formatters.toWesternDigits('१२३४५६'), equals('123456'));
      expect(Formatters.toWesternDigits('०९८७६५४३२१'), equals('0987654321'));
      expect(Formatters.toWesternDigits('9876543210'), equals('9876543210'));
    });

    test('verifyMobileOtp accepts Devanagari numerals and normalizes to Western digits', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // Passing Devanagari digits '१२३४५६' into verifyMobileOtp in demo mode
      await container.read(userProfileProvider.notifier).verifyMobileOtp(
            phone: '9876543210',
            token: '१२३४५६',
            isDemoMode: true,
          );

      final user = container.read(userProfileProvider);
      expect(user.isLoggedIn, isTrue);
    });

    test('Invalid OTP code throws exception with clean message NOT leaking 123456', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      try {
        await container.read(userProfileProvider.notifier).verifyMobileOtp(
              phone: '9876543210',
              token: '999999',
              isDemoMode: true,
            );
        fail('Expected AuthException to be thrown');
      } on AuthException catch (e) {
        expect(e.message, equals('Invalid code. Please check and try again.'));
        expect(e.message.contains('123456'), isFalse);
      }
    });

    testWidgets('OTP widget forces Western digits when typing Devanagari digits', (tester) async {
      tester.view.physicalSize = const Size(390 * 2, 844 * 2);
      tester.view.devicePixelRatio = 2.0;

      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(localeProvider.notifier).setLocale(const Locale('hi'));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            locale: Locale('hi'),
            localizationsDelegates: [
              AppLocalizations.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: Scaffold(
              body: SingleChildScrollView(
                child: OtpVerificationWidget(
                  phone: '9876543210',
                  isDemoMode: true,
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pump();

      final textFields = find.byType(TextField);
      expect(textFields, findsNWidgets(6));

      const devanagariDigits = ['१', '२', '३', '४', '५', '६'];
      for (int i = 0; i < 5; i++) {
        await tester.enterText(textFields.at(i), devanagariDigits[i]);
        await tester.pump();
      }

      // Check first 5 textfields rendered Western digits
      for (int i = 0; i < 5; i++) {
        final textFieldWidget = tester.widget<TextField>(textFields.at(i));
        expect(textFieldWidget.controller!.text, equals('${i + 1}'));
      }
    });
  });
}
