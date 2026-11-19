import '../models/pack_model.dart';
import '../models/pack_item_model.dart';
import '../models/sticker_model.dart';
import '../repositories/pack_repository.dart';
import '../repositories/sticker_repository.dart';

/// Partitioning result representation
class PartitionResult {
  final List<PackModel> readyPacks;
  final List<PackModel> incompletePacks;
  final int totalStickers;

  const PartitionResult({
    required this.readyPacks,
    required this.incompletePacks,
    required this.totalStickers,
  });
}

/// Service implementing ADR-006 (Virtual Pack Partitioning 3-30) and ADR-007 (Static/Animated Isolation)
class VirtualPackPartitioner {
  final StickerRepository _stickerRepository;
  final PackRepository _packRepository;

  static const int minPackStickers = 3;
  static const int maxPackStickers = 30;

  VirtualPackPartitioner({
    StickerRepository? stickerRepository,
    PackRepository? packRepository,
  })  : _stickerRepository = stickerRepository ?? StickerRepository(),
        _packRepository = packRepository ?? PackRepository();

  /// Synchronize persistent stickers in SQLite into partitioned WhatsApp packs
  Future<PartitionResult> partitionAndSyncPacks() async {
    final allStickers = await _stickerRepository.getAllStickers();
    final animatedList = allStickers.where((s) => s.isAnimated).toList();
    final staticList = allStickers.where((s) => !s.isAnimated).toList();

    final readyPacks = <PackModel>[];
    final incompletePacks = <PackModel>[];

    // Partition Animated Stream (ADR-007)
    await _syncStream(
      stream: animatedList,
      isAnimated: true,
      readyPacks: readyPacks,
      incompletePacks: incompletePacks,
    );

    // Partition Static Stream (ADR-007)
    await _syncStream(
      stream: staticList,
      isAnimated: false,
      readyPacks: readyPacks,
      incompletePacks: incompletePacks,
    );

    return PartitionResult(
      readyPacks: readyPacks,
      incompletePacks: incompletePacks,
      totalStickers: allStickers.length,
    );
  }

  Future<void> _syncStream({
    required List<StickerModel> stream,
    required bool isAnimated,
    required List<PackModel> readyPacks,
    required List<PackModel> incompletePacks,
  }) async {
    final prefix = isAnimated ? 'anim' : 'static';
    final typeName = isAnimated ? 'Animated' : 'Static';

    int packNumber = 1;
    for (int i = 0; i < stream.length; i += maxPackStickers) {
      final chunkEnd = (i + maxPackStickers < stream.length) ? i + maxPackStickers : stream.length;
      final chunk = stream.sublist(i, chunkEnd);
      final identifier = 'stickerdrop_pack_${prefix}_${packNumber.toString().padLeft(3, '0')}';
      final packName = 'StickerDrop $typeName $packNumber';

      // Check or create pack record in database
      var pack = await _packRepository.getPackByIdentifier(identifier);
      if (pack == null) {
        pack = await _packRepository.insertPack(PackModel(
          identifier: identifier,
          name: packName,
          publisher: 'StickerDrop User',
          trayImagePath: 'tray_icon.png',
          isAnimated: isAnimated,
          stickerCount: chunk.length,
        ));
      } else {
        await _packRepository.updateStickerCount(pack.id!, chunk.length);
        pack = pack.copyWith(stickerCount: chunk.length);
      }

      // Sync pack items
      for (int sortOrder = 0; sortOrder < chunk.length; sortOrder++) {
        final sticker = chunk[sortOrder];
        await _packRepository.addStickerToPack(PackItemModel(
          packId: pack.id!,
          stickerId: sticker.id!,
          sortOrder: sortOrder,
          emojis: isAnimated ? const ['🔥', '🗿'] : const ['👍'],
        ));
      }

      if (chunk.length >= minPackStickers) {
        readyPacks.add(pack);
      } else {
        incompletePacks.add(pack);
      }

      packNumber++;
    }
  }
}
