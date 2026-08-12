import 'package:flutter/services.dart';
import 'package:intl/intl.dart';

abstract class Formatters {
  static String currency(num amount) {
    final formatter = NumberFormat.currency(
      locale: 'en_IN',
      symbol: '₹',
      decimalDigits: 0,
    );
    return formatter.format(amount);
  }

  /// Converts any Devanagari numerals (०-९) to standard Western Arabic numerals (0-9)
  static String toWesternDigits(String input) {
    const devanagariDigits = ['०', '१', '२', '३', '४', '५', '६', '७', '८', '९'];
    String result = input;
    for (int i = 0; i < 10; i++) {
      result = result.replaceAll(devanagariDigits[i], '$i');
    }
    return result;
  }
}

/// A TextInputFormatter that automatically converts typed or pasted Devanagari numerals (०-९)
/// into standard Western Arabic numerals (0-9) in real-time.
class WesternDigitsTextInputFormatter extends TextInputFormatter {
  const WesternDigitsTextInputFormatter();

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final converted = Formatters.toWesternDigits(newValue.text);
    return newValue.copyWith(
      text: converted,
      selection: TextSelection.collapsed(offset: converted.length),
    );
  }
}
