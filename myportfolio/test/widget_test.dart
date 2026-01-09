import 'package:flutter_test/flutter_test.dart';
import 'package:myportfolio/main.dart';

void main() {
  testWidgets('Dashboard loads and shows title', (WidgetTester tester) async {
    // Mock dotenv loading if possible, or just ignore since we handle errors in main
    // But main() calls dotenv.load. In test env, assets might not be available easily without setup.
    // simpler to just pump MyApp and check for text.
    // Note: main() is async and does setup. calling MyApp() directly skips main()'s setup.
    // But MyApp doesn't depend on them being loaded successfully (it handles nulls).

    await tester.pumpWidget(const MyApp());

    // Verify that our title is present.
    expect(find.text('My Portfolio'), findsOneWidget);
    expect(find.text('12,840,340원'), findsOneWidget);

    // Verify Valuation Chart title
    expect(find.text('평가금액'), findsOneWidget);
  });
}
