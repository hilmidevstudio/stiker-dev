import 'package:flutter/material.dart';
import '../core/theme/ios_tokens.dart';
import 'screens/input_screen.dart';
import 'screens/collection_screen.dart';
import 'screens/pack_export_screen.dart';

/// Main Application Shell with iOS-fidelity TabBar navigation
class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;

  void _onStickerSaved() {
    setState(() {
      _currentIndex = 1;
    });
  }

  void _showAboutSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: IosTokens.systemBackground,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(IosTokens.radiusSheet)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(24, 12, 24, 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              // iOS Drag Grabber
              Container(
                width: 36,
                height: 5,
                decoration: BoxDecoration(
                  color: IosTokens.quaternaryLabel,
                  borderRadius: BorderRadius.circular(2.5),
                ),
              ),
              const SizedBox(height: 20),
              ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: Image.asset('assets/images/logo.png', width: 64, height: 64),
              ),
              const SizedBox(height: 12),
              const Text('StickerDrop', style: IosTokens.title1),
              const SizedBox(height: 4),
              const Text('by hilmidev.studio', style: TextStyle(fontSize: 13, color: IosTokens.tint, fontWeight: FontWeight.w600)),
              const SizedBox(height: 2),
              const Text('Version 1.0.0', style: IosTokens.footnote),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: IosTokens.systemGroupedBackground,
                  borderRadius: BorderRadius.circular(IosTokens.radiusMd),
                ),
                child: const Text(
                  'Extract stickers attached to TikTok comments and export directly into WhatsApp sticker packs.',
                  style: IosTokens.body,
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                'Crafted with love by hilmidev.studio',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: IosTokens.secondaryLabel,
                  letterSpacing: 0.2,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final screens = [
      InputScreen(onStickerSaved: _onStickerSaved),
      const CollectionScreen(),
      const PackExportScreen(),
    ];

    return Scaffold(
      backgroundColor: IosTokens.systemGroupedBackground,
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(7),
              child: Image.asset('assets/images/logo.png', width: 28, height: 28),
            ),
            const SizedBox(width: 10),
            const Text('StickerDrop', style: IosTokens.largeTitle),
          ],
        ),
        backgroundColor: IosTokens.systemBackground,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        actions: [
          IconButton(
            icon: const Icon(Icons.info_outline, size: 22, color: IosTokens.secondaryLabel),
            tooltip: 'About StickerDrop',
            onPressed: _showAboutSheet,
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: screens,
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: IosTokens.systemBackground,
          border: Border(
            top: BorderSide(color: IosTokens.hairline, width: 0.5),
          ),
        ),
        child: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: (idx) {
            setState(() => _currentIndex = idx);
          },
          backgroundColor: IosTokens.systemBackground,
          selectedItemColor: IosTokens.tint,
          unselectedItemColor: IosTokens.secondaryLabel,
          selectedLabelStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
          unselectedLabelStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.w400),
          elevation: 0,
          type: BottomNavigationBarType.fixed,
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.add_circle_outline_rounded, size: 22),
              activeIcon: Icon(Icons.add_circle_rounded, size: 22),
              label: 'Extract',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.photo_library_outlined, size: 22),
              activeIcon: Icon(Icons.photo_library, size: 22),
              label: 'Library',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.ios_share_rounded, size: 22),
              activeIcon: Icon(Icons.ios_share, size: 22),
              label: 'Export',
            ),
          ],
        ),
      ),
    );
  }
}
