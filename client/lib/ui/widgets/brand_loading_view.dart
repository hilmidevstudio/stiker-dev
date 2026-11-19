import 'package:flutter/material.dart';
import '../../core/theme/ios_tokens.dart';

/// Ultra-clean, premium Apple-style branding loading indicator
class BrandLoadingView extends StatelessWidget {
  final double iconSize;

  const BrandLoadingView({
    super.key,
    this.iconSize = 56,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Premium Squircle StickerDrop Icon
          Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(iconSize * 0.22),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.06),
                  blurRadius: 16,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(iconSize * 0.22),
              child: Image.asset(
                'assets/images/logo.png',
                width: iconSize,
                height: iconSize,
                fit: BoxFit.cover,
              ),
            ),
          ),
          const SizedBox(height: 14),

          // "StickerDrop" Title
          const Text(
            'StickerDrop',
            style: TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w600,
              letterSpacing: -0.4,
              color: Color(0xFF1C1C1E),
            ),
          ),
          const SizedBox(height: 4),

          // "hilmi dev studio" Subtitle
          const Text(
            'hilmi dev studio',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w400,
              letterSpacing: -0.1,
              color: Color(0xFF8E8E93),
            ),
          ),
          const SizedBox(height: 16),

          // Apple Style Activity Spinner
          const SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2.2,
              valueColor: AlwaysStoppedAnimation<Color>(IosTokens.tint),
            ),
          ),
        ],
      ),
    );
  }
}
