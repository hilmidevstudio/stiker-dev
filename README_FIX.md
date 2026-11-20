# StickerDrop Android Splash Resource Fix

## Problem

Android resource linking failed because `android:drawable` was assigned a raw color literal (`#FFFDF7ED`). This attribute expects a drawable resource reference.

## Files

Copy the `client` directory contents into the matching locations in your project:

- `client/android/app/src/main/res/drawable/launch_background.xml`
- `client/android/app/src/main/res/drawable-v21/launch_background.xml`
- `client/android/app/src/main/res/values/colors.xml` (new file)

The splash background remains the same warm ivory color (`#FFFDF7ED`). The XML now references `@color/launch_background_color`.

## Verify

From `client/` run:

```powershell
flutter clean
flutter build apk --debug
```

Do not uninstall the existing app or clear its data. After a successful build, verify the APK signing certificate matches the installed APK before installing it with `adb install -r`.
