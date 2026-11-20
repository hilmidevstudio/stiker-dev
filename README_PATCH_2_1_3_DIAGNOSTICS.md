# StickerDrop Patch 2.1.3 — In-app diagnostic metadata export

## Why this patch exists

Release Android apps are not debuggable, so `adb shell run-as com.stickerdrop.app` is expected to fail. This patch adds a safe in-app way to copy the selected sticker's diagnostic metadata from the Library detail sheet.

## File

Replace:
`client/lib/ui/screens/collection_screen.dart`

## What the new action does

In Library, open a sticker's detail sheet and tap **Copy diagnostic metadata**. The app copies JSON containing:
- source video ID
- source comment ID
- source author
- SHA-256
- media type and animation metadata
- dimensions, file size, frame count, duration
- local relative media path
- export status and timestamps

It intentionally excludes `original_media_url`, because CDN URLs may contain temporary access tokens. It does not export media bytes or the whole database.

## Install safety

Before updating the already-installed release APK, verify that the new APK is signed with the same signing certificate as the installed app. An update with a different signing key will be rejected. Do not uninstall the existing app because that can erase the local library.
