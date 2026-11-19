import 'package:flutter/services.dart';

/// Supported WhatsApp package variants
enum WhatsAppVariant { whatsApp, whatsAppBusiness, any }

extension WhatsAppVariantPackageName on WhatsAppVariant {
  String get packageName {
    switch (this) {
      case WhatsAppVariant.whatsApp:
        return 'com.whatsapp';
      case WhatsAppVariant.whatsAppBusiness:
        return 'com.whatsapp.w4b';
      case WhatsAppVariant.any:
        return 'com.whatsapp';
    }
  }
}

/// Bridge for triggering WhatsApp sticker pack import via Android Intent
/// Implements 07-whatsapp-integration.md Section 4
class IntentBridge {
  static const MethodChannel _channel =
      MethodChannel('com.stickerdrop.app/whatsapp_intent');

  static const String _actionEnableStickerPack =
      'com.whatsapp.intent.action.ENABLE_STICKER_PACK';

  /// Dispatches the WhatsApp ENABLE_STICKER_PACK intent
  /// Returns true if WhatsApp successfully opened the import dialog,
  /// false if WhatsApp is not installed or intent was not handled.
  Future<bool> addPackToWhatsApp({
    required String packIdentifier,
    required String packName,
    required String applicationId,
    WhatsAppVariant preferredVariant = WhatsAppVariant.any,
  }) async {
    try {
      final result = await _channel.invokeMethod<bool>(
        'addStickerPack',
        {
          'packIdentifier': packIdentifier,
          'packName': packName,
          'authority': '$applicationId.stickercontentprovider',
          'action': _actionEnableStickerPack,
        },
      );
      return result ?? false;
    } on PlatformException catch (e) {
      if (e.code == 'WHATSAPP_NOT_INSTALLED') {
        return false;
      }
      rethrow;
    }
  }

  /// Check whether a WhatsApp variant is installed on this device
  Future<bool> isWhatsAppInstalled([
    WhatsAppVariant variant = WhatsAppVariant.whatsApp,
  ]) async {
    try {
      if (variant == WhatsAppVariant.any) {
        final personal = await _channel.invokeMethod<bool>(
          'isPackageInstalled',
          {'packageName': WhatsAppVariant.whatsApp.packageName},
        );
        final business = await _channel.invokeMethod<bool>(
          'isPackageInstalled',
          {'packageName': WhatsAppVariant.whatsAppBusiness.packageName},
        );
        return (personal ?? false) || (business ?? false);
      }

      final result = await _channel.invokeMethod<bool>(
        'isPackageInstalled',
        {'packageName': variant.packageName},
      );
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }
}
