> SUPERSEDED: Use `PATCH_3_ENGINE_FOUNDATION.md` for current safe provider configuration and deployment. This older guide documents the previous paid-provider setup.

# StickerDrop Patch 2.1 — deploy and Android release guide

## Important status before deployment

Patch 2.1 fixes packaging and Android release-signing configuration on top of Patch 2. The backend test suite contains 42 passing local tests. This does **not** establish that live TikTok comment-sticker media extraction works. The active extraction adapter in this source is still **ScrapeCreators**. It requires a valid server-side `SCRAPECREATORS_API_KEY` and provider credits for live extraction. The `/v1/resolve-link` diagnostic endpoint does not call the provider and does not consume provider credits, but it only resolves link metadata; it does not fetch comments or sticker media.

Do not describe this build as a zero-token scraper or publish it as a fully working production app until real extraction and WhatsApp import have passed the acceptance tests below. No self-hosted, authorized zero-credit source for arbitrary public TikTok comment-sticker media has been implemented in this patch.

## A. What is in this ZIP

- `requirements.txt` normalized to UTF-8.
- Machine-specific `client/android/local.properties` removed. Flutter tooling recreates it for each machine.
- Python `__pycache__` / `.pyc` and generated Flutter plugin metadata removed.
- `.gitignore` now excludes machine-specific SDK config, local signing properties, and keystores.
- Android release build no longer signs with the debug certificate. It expects a locally generated upload keystore and `client/android/key.properties`.
- Existing backend behavior and the 42 local Python tests are otherwise preserved.

## B. Put the source into GitHub

1. Extract this ZIP.
2. Open the inner folder named `stiker-dev-main`. Its contents include `backend/`, `client/`, `requirements.txt`, and `Procfile`.
3. Use the **contents of that folder** as the repository root. Do not create an extra nested `stiker-dev-main/stiker-dev-main` level.
4. Commit and push the source to the GitHub branch connected to Railway.
5. Do not upload `.env`, API keys, `key.properties`, `.jks`, or `local.properties`.

## C. Deploy the backend to the existing Railway service

The Flutter client in `client/lib/core/constants/api_constants.dart` currently points to:

`https://web-production-96c4e94f.up.railway.app`

Use the existing Railway service that owns this domain unless you intentionally create a replacement service. Do not deploy the backend to Render by accident; `render.yaml` is a separate Render configuration and does not configure Railway.

1. Open Railway → the StickerDrop project → the backend service.
2. In **Settings → Source**, confirm the connected GitHub repository and production branch. If you make the GitHub repository from this ZIP, set the repository root as the service root. The root must contain `requirements.txt`, `Procfile`, and `backend/`.
3. In **Settings → Deploy**, set the start command to:

   `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

   The repository also contains a matching `Procfile`.
4. In **Variables**, add the variables needed for the current ScrapeCreators adapter:

   `EXTRACTION_PROVIDER=scrapecreators`

   `SCRAPECREATORS_BASE_URL=https://api.scrapecreators.com`

   `SCRAPECREATORS_API_KEY=<NEWLY_ROTATED_PROVIDER_KEY>`

   Add the real key only in Railway Variables. The key must not go in Flutter, GitHub, a screenshot, or this guide. Rotate/revoke the old key first if it was ever committed or exposed.
5. Review and deploy the staged Railway changes. Watch the build and deploy logs until the service is active.
6. In **Settings → Networking**, confirm the service has a public domain. Keep the existing domain if it still points to this service.

If you want to verify only the no-credit resolver first, `/health` and `/v1/resolve-link` work without making a ScrapeCreators request. The extraction endpoint cannot deliver live stickers without a working configured extraction source. Do not use `EXTRACTION_PROVIDER=mock` in production; it is for local automated tests only.

## D. Verify the backend before building the APK

Open these in a browser:

- `https://web-production-96c4e94f.up.railway.app/health`
- `https://web-production-96c4e94f.up.railway.app/docs`

The health endpoint should return JSON with `"status":"ok"`.

In Windows PowerShell, run this no-provider diagnostic test:

```powershell
$base = "https://web-production-96c4e94f.up.railway.app"
$body = @{ url = "https://vt.tiktok.com/ZS9PNxHJ49hbk-Pp13l/" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/v1/resolve-link" -ContentType "application/json" -Body $body
```

Expected fields include `success: true`, `provider_called: false`, `post_id`, `post_type`, `comment_id`, `author_id`, and `canonical_url`. Repeat for the 20 distinct short-link codes in `research/stickerdrop-user-link-corpus-2026-11-20.csv`.

This checks link resolution only. It does not validate live comment lookup or sticker download. A live `/v1/resolve-and-extract` request invokes the configured provider and may consume provider credits. Do not run a batch of live extraction tests until the provider's raw response behavior and credit implications are understood.

## E. Set up Flutter on Windows

Install:

1. Flutter SDK (stable channel) and add its `bin` directory to PATH.
2. Android Studio.
3. Android SDK Platform, Android SDK Build-Tools, Android SDK Command-line Tools, and Android SDK Platform-Tools using SDK Manager.
4. A supported JDK. Run `flutter doctor -v` and resolve Android toolchain errors before continuing.

Open PowerShell in the extracted project and run:

```powershell
cd .\stiker-dev-main\client
flutter doctor -v
flutter clean
flutter pub get
flutter analyze
flutter test
```

The `flutter pub get` / Flutter Gradle tooling will generate a machine-local `android/local.properties`. Do not commit it. If Android Studio asks for the Flutter SDK path, point it to the Flutter SDK folder installed on your PC.

## F. Create the permanent Android upload key (one time only)

Keep this key safe. Future updates to an already distributed APK must use the same signing key. Losing it can prevent users from installing updates over the existing app. Android's official signing documentation explains upload-key and Play App Signing requirements: https://developer.android.com/studio/publish/app-signing

In PowerShell:

```powershell
cd .\stiker-dev-main\client\android\app
keytool -genkeypair -v -keystore upload-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

Store the keystore password and key password securely. Back up `upload-keystore.jks` in at least two secure places that are not this Git repository.

Then:

1. Copy `client/android/key.properties.example` to `client/android/key.properties`.
2. Edit `key.properties` with the passwords you chose. Keep `keyAlias=upload`.
3. Keep `storeFile=upload-keystore.jks` because the keystore is in `client/android/app/`.
4. Never commit `key.properties` or `upload-keystore.jks`.

## G. Point the APK to the deployed backend

Open `client/lib/core/constants/api_constants.dart`.

- If the Railway domain is still `https://web-production-96c4e94f.up.railway.app`, no URL change is needed.
- If you created a different Railway domain, replace `railwayBaseUrl` with the new HTTPS domain and keep the URL without a trailing slash.

Then from `client/` run:

```powershell
flutter clean
flutter pub get
flutter analyze
flutter test
flutter build apk --release
```

APK output:

`client/build/app/outputs/flutter-apk/app-release.apk`

For Google Play, build an Android App Bundle instead:

```powershell
flutter build appbundle --release
```

AAB output:

`client/build/app/outputs/bundle/release/app-release.aab`

Google Play generally uses AAB and requires Play App Signing for new apps. Follow the Android and Flutter official release docs:

- https://docs.flutter.dev/deployment/android
- https://developer.android.com/studio/publish/app-signing

## H. Device acceptance tests — required before public release

Install the release APK on a physical Android device, then test all of these with real user-owned or otherwise authorized TikTok comment links:

1. Resolve video post comment link.
2. Resolve photo post comment link.
3. Find a sticker in a top-level comment.
4. Find a sticker in a reply thread.
5. Extract static sticker media.
6. Extract animated sticker media.
7. Reject text-only comments with a precise error (no demo media, no fake success).
8. Save sticker and restart app; confirm it persists.
9. Extract the same comment again; confirm correct deduplication without provider calls where cache is applicable.
10. Export a pack to WhatsApp and confirm it appears and stickers send correctly.
11. Repeat on WhatsApp Business if that integration is intended to be supported.
12. Test airplane mode / CDN timeout / malformed URL and confirm honest error messages.

Release gate: all intended extraction cases must use the correct target comment ID and original media bytes, and WhatsApp import must work. The 42 Python tests do not replace this live acceptance run.

## I. Current scraper choice and zero-credit goal

The implementation in this patch still uses ScrapeCreators for live extraction. Its API key is a backend-only secret and provider usage may incur credits. The no-credit `/v1/resolve-link` endpoint is only a link resolver; it is not the sticker scraper.

A true zero-provider-credit architecture requires a separate, lawful and technically verified source that returns the sticker media attached to the target comment. That source has not yet been implemented or demonstrated in this repository. Until that blocker is solved, the app can be packaged as a diagnostic/staging APK, but it is not honestly ready to be called the finished free StickerDrop release.
