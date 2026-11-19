import 'package:flutter/material.dart';
import '../../features/collection/models/pack_model.dart';
import '../../features/collection/models/sticker_model.dart';
import '../../features/collection/models/pack_item_model.dart';
import '../../features/collection/storage/sha256_storage_manager.dart';

/// Card widget presenting a virtual WhatsApp pack and export action
class PackCard extends StatelessWidget {
  final PackModel pack;
  final List<StickerModel> stickers;
  final List<PackItemModel> items;
  final Sha256StorageManager? storageManager;
  final bool isExporting;
  final VoidCallback? onExport;

  const PackCard({
    super.key,
    required this.pack,
    required this.stickers,
    required this.items,
    this.storageManager,
    this.isExporting = false,
    this.onExport,
  });

  @override
  Widget build(BuildContext context) {
    final count = stickers.length;
    final isReady = count >= 3 && count <= 30;
    final needed = 3 - count;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE5E5EA)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.02),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Row
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(7),
                decoration: BoxDecoration(
                  color: const Color(0xFFF2F2F7),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  pack.isAnimated ? Icons.movie_outlined : Icons.image_outlined,
                  color: const Color(0xFF1C1C1E),
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      pack.name,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 15,
                        color: Color(0xFF1C1C1E),
                      ),
                    ),
                    Text(
                      '$count / 30 stickers',
                      style: const TextStyle(color: Color(0xFF8E8E93), fontSize: 12),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: isReady ? const Color(0xFFE8F5E9) : const Color(0xFFF2F2F7),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  isReady ? 'Ready' : 'Need $needed more',
                  style: TextStyle(
                    color: isReady ? const Color(0xFF2E7D32) : const Color(0xFF8E8E93),
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Horizontal Stickers Preview List
          SizedBox(
            height: 64,
            child: stickers.isEmpty
                ? const Center(
                    child: Text(
                      'No stickers assigned yet',
                      style: TextStyle(color: Color(0xFF8E8E93), fontSize: 12),
                    ),
                  )
                : ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: stickers.length,
                    separatorBuilder: (_, __) => const SizedBox(width: 8),
                    itemBuilder: (context, idx) {
                      final sticker = stickers[idx];
                      final file = storageManager?.getFileForRelativePath(sticker.localMediaPath);

                      return Container(
                        width: 64,
                        height: 64,
                        decoration: BoxDecoration(
                          color: const Color(0xFFF2F2F7),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFFE5E5EA)),
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: file != null && file.existsSync()
                              ? Image.file(file, fit: BoxFit.contain)
                              : Image.network(
                                  sticker.originalMediaUrl,
                                  fit: BoxFit.contain,
                                  errorBuilder: (_, __, ___) => const Icon(
                                    Icons.image_outlined,
                                    size: 20,
                                    color: Color(0xFF8E8E93),
                                  ),
                                ),
                        ),
                      );
                    },
                  ),
          ),
          const SizedBox(height: 12),

          // Action / Export Button
          SizedBox(
            width: double.infinity,
            height: 42,
            child: ElevatedButton(
              onPressed: isReady && !isExporting ? onExport : null,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF25D366),
                foregroundColor: Colors.white,
                disabledBackgroundColor: const Color(0xFFE5E5EA),
                disabledForegroundColor: const Color(0xFF8E8E93),
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              child: isExporting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : Text(
                      isReady ? 'Add to WhatsApp' : 'Minimum 3 stickers required',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: isReady ? Colors.white : const Color(0xFF8E8E93),
                      ),
                    ),
            ),
          ),
        ],
      ),
    );
  }
}
