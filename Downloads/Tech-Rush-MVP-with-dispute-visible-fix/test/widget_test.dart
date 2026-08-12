import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:kaamsetu/main.dart';

void main() {
  testWidgets('App renders without crashing test', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: KaamSetuApp(),
      ),
    );
  });
}
