# StickerDrop Patch 2.1.1 - Flutter analyzer fixes

This patch contains two Dart changes based on the `flutter analyze` output:

1. `client/test/core/network/api_client_test.dart`
   - Removed the obsolete `provider: 'mock'` argument from `ApiClient.resolveAndExtract()`.
   - Provider selection is handled by the backend configuration; the current Flutter API method accepts only `url`.

2. `client/lib/ui/screens/pack_export_screen.dart`
   - Added `if (!mounted) return;` immediately after awaiting `isWhatsAppInstalled()`.
   - This prevents using the widget's `BuildContext` if the screen was disposed during that asynchronous call.

No extraction/provider behavior or production API payload was changed by this patch.

## Apply

Replace the corresponding files in your local project with the versions in this archive, or use the complete source archive. Then run from `client/`:

```powershell
flutter analyze
flutter test
```

This environment did not have Flutter/Dart installed, so these two commands must be run on the developer machine to confirm the analyzer output.
