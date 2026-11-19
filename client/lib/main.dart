import 'package:flutter/material.dart';
import 'core/theme/ios_tokens.dart';
import 'ui/main_shell.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const StickerDropApp());
}

class StickerDropApp extends StatelessWidget {
  const StickerDropApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'StickerDrop',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: IosTokens.systemGroupedBackground,
        colorScheme: const ColorScheme.light(
          primary: IosTokens.tint,
          secondary: IosTokens.success,
          surface: IosTokens.systemBackground,
          onSurface: IosTokens.label,
          error: IosTokens.destructive,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: IosTokens.systemBackground,
          foregroundColor: IosTokens.label,
          centerTitle: false,
          elevation: 0,
          scrolledUnderElevation: 0.5,
          titleTextStyle: IosTokens.title1,
        ),
        dividerColor: IosTokens.hairline,
      ),
      home: const MainShell(),
    );
  }
}
