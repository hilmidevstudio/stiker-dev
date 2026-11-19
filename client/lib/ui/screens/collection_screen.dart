import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import '../../core/theme/ios_tokens.dart';
import '../../features/collection/models/sticker_model.dart';
import '../../features/collection/repositories/sticker_repository.dart';
import '../../features/collection/storage/sha256_storage_manager.dart';
import '../../features/collection/services/virtual_pack_partitioner.dart';
import '../widgets/sticker_tile.dart';
import '../widgets/brand_loading_view.dart';
import '../widgets/app_footer.dart';

/// Screen 2: Local SQLite Sticker Collection Gallery
class CollectionScreen extends StatefulWidget {
  const CollectionScreen({super.key});

  @override
  State<CollectionScreen> createState() => _CollectionScreenState();
}

class _CollectionScreenState extends State<CollectionScreen> {
  final StickerRepository _stickerRepository = StickerRepository();
  Sha256StorageManager? _storageManager;

  List<StickerModel> _stickers = [];
  bool _isLoading = true;
  String _filter = 'all'; // 'all', 'animated', 'static'

  @override
  void initState() {
    super.initState();
    _loadCollection();
  }

  Future<void> _loadCollection() async {
    setState(() => _isLoading = true);
    try {
      final docsDir = await getApplicationDocumentsDirectory();
      _storageManager = Sha256StorageManager(baseDir: docsDir);

      bool? isAnimated;
      if (_filter == 'animated') isAnimated = true;
      if (_filter == 'static') isAnimated = false;

      final stickers = await _stickerRepository.getAllStickers(isAnimated: isAnimated);
      setState(() {
        _stickers = stickers;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error loading collection: $e'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _deleteSticker(StickerModel sticker) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: IosTokens.systemBackground,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(IosTokens.radiusLg)),
        title: const Text('Delete Sticker', style: IosTokens.title2),
        content: Text(
          'Remove this sticker from ${sticker.sourceAuthor}? This will also update virtual packs.',
          style: IosTokens.callout,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel', style: TextStyle(color: IosTokens.tint, fontSize: 15)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text(
              'Delete',
              style: TextStyle(color: IosTokens.destructive, fontWeight: FontWeight.w600, fontSize: 15),
            ),
          ),
        ],
      ),
    );

    if (confirmed == true && sticker.id != null) {
      await _stickerRepository.deleteSticker(sticker.id!);
      if (_storageManager != null) {
        await _storageManager!.deleteMediaFile(sticker.localMediaPath);
      }
      await VirtualPackPartitioner().partitionAndSyncPacks();
      _loadCollection();

      if (mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Sticker removed from library.'),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(IosTokens.radiusMd)),
          ),
        );
      }
    }
  }

  void _showStickerDetails(StickerModel sticker) {
    showModalBottomSheet(
      context: context,
      backgroundColor: IosTokens.systemBackground,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(IosTokens.radiusSheet)),
      ),
      builder: (ctx) {
        final mediaFile = _storageManager?.getFileForRelativePath(sticker.localMediaPath);

        return Padding(
          padding: EdgeInsets.only(
            top: 14,
            left: 20,
            right: 20,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 28,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              // iOS Grabber
              Container(
                width: 36,
                height: 5,
                decoration: BoxDecoration(
                  color: IosTokens.quaternaryLabel,
                  borderRadius: BorderRadius.circular(2.5),
                ),
              ),
              const SizedBox(height: 18),

              // Preview Media Box
              Container(
                width: 130,
                height: 130,
                decoration: BoxDecoration(
                  color: IosTokens.systemGroupedBackground,
                  borderRadius: BorderRadius.circular(IosTokens.radiusLg),
                  border: Border.all(color: IosTokens.hairline),
                ),
                padding: const EdgeInsets.all(8),
                child: mediaFile != null && mediaFile.existsSync()
                    ? Image.file(mediaFile, fit: BoxFit.contain)
                    : Image.network(sticker.originalMediaUrl, fit: BoxFit.contain),
              ),
              const SizedBox(height: 14),

              Text('@${sticker.sourceAuthor.replaceFirst('@', '')}', style: IosTokens.title2),
              const SizedBox(height: 16),

              // iOS Inset Grouped Details Box
              Container(
                decoration: BoxDecoration(
                  color: IosTokens.systemGroupedBackground,
                  borderRadius: BorderRadius.circular(IosTokens.radiusMd),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                child: Column(
                  children: [
                    _detailRow('Platform', sticker.sourcePlatform.toUpperCase()),
                    const Divider(height: 12, color: IosTokens.hairline),
                    _detailRow('Type', sticker.isAnimated ? 'Animated AWEBP' : 'Static WEBP'),
                    const Divider(height: 12, color: IosTokens.hairline),
                    _detailRow('Dimensions', '${sticker.width} × ${sticker.height} px'),
                    const Divider(height: 12, color: IosTokens.hairline),
                    _detailRow('Size', '${(sticker.fileSize / 1024).toStringAsFixed(1)} KB'),
                    const Divider(height: 12, color: IosTokens.hairline),
                    _detailRow('Status', sticker.exportStatus),
                    const Divider(height: 12, color: IosTokens.hairline),
                    _detailRow('SHA-256', '${sticker.sha256.substring(0, 14)}...'),
                  ],
                ),
              ),
              const SizedBox(height: 20),

              // iOS Action Buttons
              Row(
                children: [
                  Expanded(
                    child: SizedBox(
                      height: 44,
                      child: OutlinedButton(
                        onPressed: () {
                          Clipboard.setData(ClipboardData(text: sticker.sha256));
                          Navigator.pop(ctx);
                          ScaffoldMessenger.of(context).clearSnackBars();
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: const Text('SHA-256 hash copied.'),
                              behavior: SnackBarBehavior.floating,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(IosTokens.radiusMd)),
                            ),
                          );
                        },
                        style: OutlinedButton.styleFrom(
                          foregroundColor: IosTokens.tint,
                          side: const BorderSide(color: IosTokens.hairline),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(IosTokens.radiusMd)),
                        ),
                        child: const Text('Copy SHA', style: TextStyle(fontWeight: FontWeight.w600)),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: SizedBox(
                      height: 44,
                      child: ElevatedButton(
                        onPressed: () {
                          Navigator.pop(ctx);
                          _deleteSticker(sticker);
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: IosTokens.destructive,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(IosTokens.radiusMd)),
                        ),
                        child: const Text('Delete', style: TextStyle(fontWeight: FontWeight.w600)),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: IosTokens.subheadline),
          Text(
            value,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: IosTokens.label,
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // iOS Segmented Control Bar
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
          child: Row(
            children: [
              _buildSegmentedFilter(),
              const Spacer(),
              Text(
                '${_stickers.length}',
                style: const TextStyle(
                  color: Color(0xFF8E8E93),
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),

        // Grid Content
        Expanded(
          child: _isLoading
              ? const BrandLoadingView()
              : _stickers.isEmpty
                  ? _buildEmptyState()
                  : RefreshIndicator(
                      onRefresh: _loadCollection,
                      child: GridView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 3,
                          childAspectRatio: 0.85,
                          crossAxisSpacing: 12,
                          mainAxisSpacing: 12,
                        ),
                        itemCount: _stickers.length,
                        itemBuilder: (context, index) {
                          final sticker = _stickers[index];
                          final file = _storageManager?.getFileForRelativePath(sticker.localMediaPath);
                          return StickerTile(
                            sticker: sticker,
                            mediaFile: file,
                            onTap: () => _showStickerDetails(sticker),
                          );
                        },
                      ),
                    ),
        ),
      ],
    );
  }

  Widget _buildSegmentedFilter() {
    final options = [
      {'label': 'All', 'value': 'all'},
      {'label': 'Animated', 'value': 'animated'},
      {'label': 'Static', 'value': 'static'},
    ];

    return Container(
      height: 32,
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        color: const Color(0xFFE5E5EA),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: options.map((opt) {
          final isSelected = _filter == opt['value'];
          return GestureDetector(
            onTap: () {
              setState(() => _filter = opt['value']!);
              _loadCollection();
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              padding: const EdgeInsets.symmetric(horizontal: 14),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: isSelected ? Colors.white : Colors.transparent,
                borderRadius: BorderRadius.circular(6),
                boxShadow: isSelected
                    ? [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.06),
                          blurRadius: 4,
                          offset: const Offset(0, 1),
                        )
                      ]
                    : null,
              ),
              child: Text(
                opt['label']!,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                  color: isSelected ? const Color(0xFF1C1C1E) : const Color(0xFF8E8E93),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(
                color: Color(0xFFE5E5EA),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.photo_library_outlined, size: 36, color: Color(0xFF8E8E93)),
            ),
            const SizedBox(height: 16),
            const Text(
              'No Stickers in Library',
              style: TextStyle(
                color: Color(0xFF1C1C1E),
                fontSize: 17,
                fontWeight: FontWeight.w600,
                letterSpacing: -0.3,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Extract stickers from TikTok comments in the Extract tab.',
              style: TextStyle(color: Color(0xFF8E8E93), fontSize: 13),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 28),
            const AppFooter(),
          ],
        ),
      ),
    );
  }
}
