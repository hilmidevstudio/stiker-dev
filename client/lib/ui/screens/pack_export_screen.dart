import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import '../../core/theme/ios_tokens.dart';
import '../../features/collection/models/pack_model.dart';
import '../../features/collection/models/sticker_model.dart';
import '../../features/collection/models/pack_item_model.dart';
import '../../features/collection/repositories/pack_repository.dart';
import '../../features/collection/repositories/sticker_repository.dart';
import '../../features/collection/storage/sha256_storage_manager.dart';
import '../../features/collection/services/virtual_pack_partitioner.dart';
import '../../features/whatsapp_export/whatsapp_content_provider.dart';
import '../../features/whatsapp_export/intent_bridge.dart';
import '../widgets/brand_loading_view.dart';
import '../widgets/pack_card.dart';
import '../widgets/app_footer.dart';

/// Screen 3: WhatsApp Virtual Pack Partitioning & Native Intent Export
class PackExportScreen extends StatefulWidget {
  const PackExportScreen({super.key});

  @override
  State<PackExportScreen> createState() => _PackExportScreenState();
}

class _PackExportScreenState extends State<PackExportScreen> {
  final PackRepository _packRepository = PackRepository();
  final StickerRepository _stickerRepository = StickerRepository();
  final IntentBridge _intentBridge = IntentBridge();
  final WhatsAppContentProvider _contentProvider = WhatsAppContentProvider();

  Sha256StorageManager? _storageManager;
  Directory? _appDocsDir;

  List<PackModel> _animatedPacks = [];
  List<PackModel> _staticPacks = [];
  Map<int, List<StickerModel>> _packStickersMap = {};
  Map<int, List<PackItemModel>> _packItemsMap = {};

  bool _isLoading = true;
  String? _exportingPackId;

  @override
  void initState() {
    super.initState();
    _loadPacks();
  }

  Future<void> _loadPacks() async {
    setState(() => _isLoading = true);
    try {
      _appDocsDir = await getApplicationDocumentsDirectory();
      _storageManager = Sha256StorageManager(baseDir: _appDocsDir!);

      // 1. Sync Virtual Packs from current collection (ADR-006 & ADR-007)
      final partitioner = VirtualPackPartitioner(
        stickerRepository: _stickerRepository,
        packRepository: _packRepository,
      );
      await partitioner.partitionAndSyncPacks();

      // 2. Load packs
      final animPacks = await _packRepository.getAllPacks(isAnimated: true);
      final statPacks = await _packRepository.getAllPacks(isAnimated: false);

      final stickersMap = <int, List<StickerModel>>{};
      final itemsMap = <int, List<PackItemModel>>{};

      for (final pack in [...animPacks, ...statPacks]) {
        if (pack.id == null) continue;
        final items = await _packRepository.getPackItems(pack.id!);
        itemsMap[pack.id!] = items;

        final stickerList = <StickerModel>[];
        for (final item in items) {
          final s = await _stickerRepository.getStickerById(item.stickerId);
          if (s != null) stickerList.add(s);
        }
        stickersMap[pack.id!] = stickerList;
      }

      setState(() {
        _animatedPacks = animPacks;
        _staticPacks = statPacks;
        _packStickersMap = stickersMap;
        _packItemsMap = itemsMap;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error loading packs: $e'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _exportPackToWhatsApp(PackModel pack) async {
    setState(() => _exportingPackId = pack.identifier);

    try {
      if (_appDocsDir == null || _storageManager == null) {
        throw StateError('Storage not initialized');
      }

      // Step 1: Export pack files and contents.json to local filesystem
      await _contentProvider.exportPackDirectory(
        pack: pack,
        baseDir: _appDocsDir!,
        storageManager: _storageManager!,
      );

      // Step 2: Invoke Android Native Intent Bridge
      final success = await _intentBridge.addPackToWhatsApp(
        packIdentifier: pack.identifier,
        packName: pack.name,
        applicationId: 'com.stickerdrop.app',
      );

      if (mounted) {
        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('WhatsApp import dialog launched for "${pack.name}"!'),
              backgroundColor: const Color(0xFF25D366),
            ),
          );
        } else {
          _showWhatsAppNotInstalledDialog();
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('WhatsApp export failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _exportingPackId = null);
    }
  }

  void _showWhatsAppNotInstalledDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: IosTokens.systemBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(IosTokens.radiusLg)),
        title: const Text('WhatsApp Not Found', style: IosTokens.title2),
        content: const Text(
          'Neither WhatsApp nor WhatsApp Business was detected on this device.\n\n'
          'Please install WhatsApp from the Google Play Store to import custom sticker packs.',
          style: IosTokens.callout,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('OK', style: TextStyle(color: IosTokens.tint, fontSize: 16, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return _isLoading
        ? const BrandLoadingView()
        : RefreshIndicator(
            onRefresh: _loadPacks,
            child: ListView(
              padding: const EdgeInsets.only(top: 12, bottom: 24),
              children: [
                // Clean iOS Info Footnote Banner
                Container(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFFE5E5EA)),
                  ),
                  child: const Text(
                    'WhatsApp requires 3 to 30 stickers per pack. Animated and static stickers are organized into separate packs.',
                    style: TextStyle(color: Color(0xFF8E8E93), fontSize: 12, height: 1.3),
                  ),
                ),

                const SizedBox(height: 8),

                // Section 1: Animated Packs (Stream A)
                _buildSectionHeader('Animated Packs', _animatedPacks.length),
                if (_animatedPacks.isEmpty)
                  _buildNoPacksNotice('animated')
                else
                  ..._animatedPacks.map((pack) {
                    final stickers = _packStickersMap[pack.id] ?? [];
                    final items = _packItemsMap[pack.id] ?? [];
                    return PackCard(
                      pack: pack,
                      stickers: stickers,
                      items: items,
                      storageManager: _storageManager,
                      isExporting: _exportingPackId == pack.identifier,
                      onExport: () => _exportPackToWhatsApp(pack),
                    );
                  }),

                const SizedBox(height: 16),

                // Section 2: Static Packs (Stream B)
                _buildSectionHeader('Static Packs', _staticPacks.length),
                if (_staticPacks.isEmpty)
                  _buildNoPacksNotice('static')
                else
                  ..._staticPacks.map((pack) {
                    final stickers = _packStickersMap[pack.id] ?? [];
                    final items = _packItemsMap[pack.id] ?? [];
                    return PackCard(
                      pack: pack,
                      stickers: stickers,
                      items: items,
                      storageManager: _storageManager,
                      isExporting: _exportingPackId == pack.identifier,
                      onExport: () => _exportPackToWhatsApp(pack),
                    );
                  }),

                const SizedBox(height: 16),
                const AppFooter(),
              ],
            ),
          );
  }

  Widget _buildSectionHeader(String title, int count) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 12, 16, 6),
      child: Row(
        children: [
          Text(
            title,
            style: const TextStyle(
              fontWeight: FontWeight.w700,
              fontSize: 16,
              letterSpacing: -0.3,
              color: Color(0xFF1C1C1E),
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
            decoration: BoxDecoration(
              color: const Color(0xFFE5E5EA),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              '$count',
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: Color(0xFF8E8E93),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNoPacksNotice(String type) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFE5E5EA)),
        ),
        child: Text(
          'No $type stickers saved yet. Extract $type stickers to generate WhatsApp packs.',
          style: const TextStyle(color: Color(0xFF8E8E93), fontSize: 13),
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}
