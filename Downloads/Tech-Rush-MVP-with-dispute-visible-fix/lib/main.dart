import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'core/theme.dart';
import 'l10n/app_localizations.dart';
import 'providers/locale_provider.dart';
import 'routing/app_router.dart';
import 'services/supabase_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Supabase client
  await SupabaseService.initialize();

  // Session refresh guard on app launch
  final session = Supabase.instance.client.auth.currentSession;
  if (session != null && session.isExpired) {
    try {
      await Supabase.instance.client.auth.refreshSession();
    } catch (_) {
      // Ignore refresh errors on launch, let the auth guard handle it later
    }
  }

  runApp(
    const ProviderScope(
      child: KaamSetuApp(),
    ),
  );
}

class KaamSetuApp extends ConsumerWidget {
  const KaamSetuApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    final currentLocale = ref.watch(localeProvider);

    return MaterialApp.router(
      title: 'KaamSetu',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      routerConfig: router,
      locale: currentLocale,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
    );
  }
}
