import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import '../../core/theme/ios_tokens.dart';
import '../../core/network/api_exceptions.dart';
import '../../features/extraction/models/extraction_response.dart';
import '../../features/extraction/services/extraction_service.dart';
import '../../features/collection/models/sticker_model.dart';
import '../../features/collection/repositories/sticker_repository.dart';
import '../../features/collection/storage/sha256_storage_manager.dart';
import '../../features/collection/services/virtual_pack_partitioner.dart';
import '../widgets/brand_loading_view.dart';
import '../widgets/app_footer.dart';

/// Screen 1: TikTok link input, Backend Proxy extraction, and Saving to Collection
class InputScreen extends StatefulWidget {
  final VoidCallback? onStickerSaved;

  const InputScreen({super.key, this.onStickerSaved});

  @override
  State<InputScreen> createState() => _InputScreenState();
}

class _InputScreenState extends State<InputScreen> {
  final TextEditingController _urlController = TextEditingController();
  final ExtractionService _extractionService = ExtractionService();
  final StickerRepository _stickerRepository = StickerRepository();

  bool _isLoading = false;
  bool _isSaving = false;
  String? _errorMessage;
  ExtractionResponse? _extractedResponse;
  String? _saveStatusMessage;

  @override
  void dispose() {
    _urlController.dispose();
    _extractionService.dispose();
    super.dispose();
  }

  Future<void> _pasteFromClipboard() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    if (data?.text != null && data!.text!.isNotEmpty) {
      setState(() {
        _urlController.text = data.text!.trim();
        _errorMessage = null;
      });
    }
  }

  Future<void> _extractSticker() async {
    final rawUrl = _urlController.text.trim();
    if (rawUrl.isEmpty) {
      setState(() => _errorMessage = 'Please enter or paste a TikTok link.');
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _extractedResponse = null;
      _saveStatusMessage = null;
    });

    try {
      final response = await _extractionService.extractFromUrl(rawInput: rawUrl);
      setState(() {
        _extractedResponse = response;
      });
    } on ApiException catch (e) {
      setState(() {
        _errorMessage = '${e.errorCode}: ${e.message}';
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Extraction failed: $e';
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _saveToCollection() async {
    final res = _extractedResponse;
    if (res == null) return;

    setState(() => _isSaving = true);

    try {
      final docsDir = await getApplicationDocumentsDirectory();
      final storageManager = Sha256StorageManager(baseDir: docsDir);

      // 1. Download media bytes from CDN
      final mediaUrl = res.sticker.mediaUrl;
      final bytes = await _extractionService.downloadMedia(mediaUrl);

      // 2. Save file via SHA-256 Content-Addressed Storage (ADR-005 Gate 2)
      final storageResult = await storageManager.saveMediaBytes(
        bytes: bytes,
        extension: res.sticker.format,
      );

      // 3. Insert or Deduplicate into SQLite Repository (ADR-002 & ADR-005)
      final model = StickerModel(
        sourceVideoId: res.videoId,
        sourceCommentId: res.commentId,
        sourceAuthor: '@${res.author.uniqueId}',
        stickerId: res.sticker.stickerId,
        originalMediaUrl: res.sticker.mediaUrl,
        localMediaPath: storageResult.relativePath,
        mediaType: res.sticker.isAnimated ? 'image/awebp' : 'image/webp',
        isAnimated: res.sticker.isAnimated,
        width: res.sticker.width,
        height: res.sticker.height,
        fileSize: storageResult.fileSize,
        sha256: storageResult.sha256,
      );

      final saved = await _stickerRepository.insertSticker(model);

      // 4. Auto-sync Virtual Packs (ADR-006 & ADR-007)
      final partitioner = VirtualPackPartitioner();
      await partitioner.partitionAndSyncPacks();

      final isExisting = storageResult.isExistingFile || (saved.id != null && saved.id != model.id);
      final msg = isExisting
          ? 'Sticker already in collection! (Deduplication matched ${saved.sourceCommentId})'
          : 'Sticker successfully saved to collection!';

      setState(() {
        _saveStatusMessage = msg;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(msg),
            backgroundColor: isExisting ? IosTokens.warning : IosTokens.success,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(IosTokens.radiusMd)),
          ),
        );
        widget.onStickerSaved?.call();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save sticker: $e'),
            backgroundColor: IosTokens.destructive,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(IosTokens.radiusMd)),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // iOS Clean Section Header
          const Padding(
            padding: EdgeInsets.only(left: 4, top: 4, bottom: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Extract Sticker',
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w700,
                    letterSpacing: -0.5,
                    color: Color(0xFF1C1C1E),
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  'Paste a TikTok comment link to extract sticker packs.',
                  style: TextStyle(
                    fontSize: 14,
                    color: Color(0xFF8E8E93),
                  ),
                ),
              ],
            ),
          ),

          // iOS Style Search / Input Field
          Container(
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFE5E5EA)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.02),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
            child: Row(
              children: [
                const Icon(Icons.link_rounded, color: Color(0xFF8E8E93), size: 20),
                const SizedBox(width: 10),
                Expanded(
                  child: TextField(
                    controller: _urlController,
                    decoration: const InputDecoration(
                      hintText: 'https://vt.tiktok.com/...',
                      hintStyle: TextStyle(color: Color(0xFFC7C7CC), fontSize: 14),
                      border: InputBorder.none,
                      isDense: true,
                    ),
                    style: const TextStyle(fontSize: 14, color: Color(0xFF1C1C1E)),
                    keyboardType: TextInputType.url,
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _extractSticker(),
                  ),
                ),
                if (_urlController.text.isNotEmpty)
                  GestureDetector(
                    onTap: () {
                      _urlController.clear();
                      setState(() {
                        _errorMessage = null;
                        _extractedResponse = null;
                      });
                    },
                    child: const Padding(
                      padding: EdgeInsets.all(4.0),
                      child: Icon(Icons.cancel, color: Color(0xFFC7C7CC), size: 18),
                    ),
                  ),
                TextButton(
                  onPressed: _pasteFromClipboard,
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: const Text(
                    'Paste',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF007AFF)),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // iOS Action Button
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton(
              onPressed: _isLoading ? null : _extractSticker,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF007AFF),
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: _isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text(
                      'Extract Sticker',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: -0.2),
                    ),
            ),
          ),

          // Loading State with Premium Branding
          if (_isLoading) ...[
            const SizedBox(height: 36),
            const BrandLoadingView(iconSize: 56),
          ],

          // iOS Clean Error Banner
          if (_errorMessage != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFFFFEBEE),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFFFCDD2)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.error_outline, color: Color(0xFFD32F2F), size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _errorMessage!,
                      style: const TextStyle(color: Color(0xFFB71C1C), fontSize: 13, height: 1.3),
                    ),
                  ),
                ],
              ),
            ),
          ],

          // Extracted Sticker Result Card
          if (_extractedResponse != null) ...[
            const SizedBox(height: 20),
            _buildExtractionPreviewCard(_extractedResponse!),
          ],

          const SizedBox(height: 24),
          const AppFooter(),
        ],
      ),
    );
  }

  Widget _buildExtractionPreviewCard(ExtractionResponse res) {
    final sticker = res.sticker;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE5E5EA)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                backgroundImage: res.author.avatarUrl.isNotEmpty
                    ? NetworkImage(res.author.avatarUrl)
                    : null,
                radius: 18,
                backgroundColor: const Color(0xFFF2F2F7),
                child: res.author.avatarUrl.isEmpty
                    ? const Icon(Icons.person, size: 18, color: Color(0xFF8E8E93))
                    : null,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '@${res.author.uniqueId}',
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                        color: Color(0xFF1C1C1E),
                      ),
                    ),
                    if (res.commentText.isNotEmpty)
                      Text(
                        res.commentText,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Color(0xFF8E8E93), fontSize: 12),
                      ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFFF2F2F7),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  sticker.isAnimated ? 'Animated' : 'Static',
                  style: const TextStyle(
                    color: Color(0xFF1C1C1E),
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const Divider(height: 24, color: Color(0xFFE5E5EA)),

          // Sticker Media Image Preview
          Center(
            child: Container(
              constraints: const BoxConstraints(maxHeight: 180, maxWidth: 180),
              decoration: BoxDecoration(
                color: const Color(0xFFF2F2F7),
                borderRadius: BorderRadius.circular(12),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.network(
                  sticker.mediaUrl,
                  fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => const Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.broken_image_outlined, size: 36, color: Color(0xFF8E8E93)),
                        SizedBox(height: 4),
                        Text('Unable to preview media', style: TextStyle(fontSize: 11, color: Color(0xFF8E8E93))),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Technical Specifications
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              _chip('Format', sticker.format.toUpperCase()),
              _chip('Size', '${sticker.width}×${sticker.height} px'),
              _chip('Provider', res.providerUsed),
              _chip('ID', res.commentId),
            ],
          ),
          const SizedBox(height: 16),

          // Save Button
          SizedBox(
            width: double.infinity,
            height: 44,
            child: ElevatedButton(
              onPressed: _isSaving ? null : _saveToCollection,
              style: ElevatedButton.styleFrom(
                backgroundColor: IosTokens.tint, // iOS System Blue
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: _isSaving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text(
                      'Save to Library',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                    ),
            ),
          ),

          if (_saveStatusMessage != null) ...[
            const SizedBox(height: 8),
            Text(
              _saveStatusMessage!,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: IosTokens.tint,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _chip(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFFF2F2F7),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        '$label: $value',
        style: const TextStyle(fontSize: 11, color: Color(0xFF3C3C43), fontWeight: FontWeight.w500),
      ),
    );
  }
}
