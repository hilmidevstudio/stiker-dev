import 'dart:io';
import 'package:flutter/material.dart';
import '../../features/collection/models/sticker_model.dart';

/// Reusable sticker thumbnail tile
class StickerTile extends StatelessWidget {
  final StickerModel sticker;
  final File? mediaFile;
  final VoidCallback? onTap;

  const StickerTile({
    super.key,
    required this.sticker,
    this.mediaFile,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final isAnimated = sticker.isAnimated;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFE5E5EA)),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Stack(
          fit: StackFit.expand,
          children: [
            // Media Image or Placeholder
            Padding(
              padding: const EdgeInsets.all(8.0),
              child: mediaFile != null && mediaFile!.existsSync()
                  ? Image.file(
                      mediaFile!,
                      fit: BoxFit.contain,
                      errorBuilder: (_, __, ___) => _buildPlaceholder(),
                    )
                  : sticker.originalMediaUrl.isNotEmpty
                      ? Image.network(
                          sticker.originalMediaUrl,
                          fit: BoxFit.contain,
                          errorBuilder: (_, __, ___) => _buildPlaceholder(),
                        )
                      : _buildPlaceholder(),
            ),

            // Top-right Animated Indicator
            if (isAnimated)
              Positioned(
                top: 6,
                right: 6,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.black.withOpacity(0.65),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'ANIM',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 8,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.2,
                    ),
                  ),
                ),
              ),

            // Bottom subtle author bar
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                decoration: const BoxDecoration(
                  color: Colors.white,
                  border: Border(top: BorderSide(color: Color(0xFFF2F2F7), width: 1)),
                ),
                child: Text(
                  sticker.sourceAuthor,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Color(0xFF1C1C1E),
                    fontSize: 10,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPlaceholder() {
    return Container(
      color: Colors.grey.shade200,
      child: const Center(
        child: Icon(Icons.image, size: 36, color: Colors.grey),
      ),
    );
  }
}
