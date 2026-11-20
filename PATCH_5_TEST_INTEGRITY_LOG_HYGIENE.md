# StickerDrop Patch 5 — Test Integrity, Log Hygiene & Safe Source Bundles

## Scope

Patch 5 hardens the existing Patch 4 backend without changing extraction-provider selection or pretending that a TikTok scraper has been implemented.

### 1. Async adapter tests now actually execute

`tests/backend/test_extractor_adapter.py` now uses `unittest.IsolatedAsyncioTestCase`. The ScrapeCreators comment-page test and ScrapeSocial reply-page test are awaited by the test runner and assert that the mocked upstream call was awaited with the expected endpoint and parameters.

Before this fix, the tests were declared as `async def` methods on `unittest.TestCase`. The runner counted them as successful test methods without awaiting their coroutines, producing `RuntimeWarning: coroutine ... was never awaited`.

### 2. Raw URLs and upstream response bodies are not exposed in routine errors

- Link-resolution errors no longer embed the original malformed input or full canonical URL.
- Provider HTTP errors no longer include `response.text`.
- Provider network errors no longer include exception strings that can contain signed request URLs.
- FastAPI exception handlers log only the route and stable error code/type, not exception text or raw tracebacks.
- Request-validation responses include only field locations and error types. Pydantic's raw `input` value is omitted.
- Generic internal errors return a safe message and route only.

The app still returns useful machine-readable error codes and safe status information. Detailed upstream payloads must not be used as routine logs because they may contain signed CDN URLs, user identifiers, or provider diagnostics.

### 3. Safe source-bundle script

Run this at the project root on Windows:

```powershell
python scripts/create_source_bundle.py
```

The script creates a sibling ZIP named `stiker-dev-source-bundle.zip` (using the current project folder name). It excludes:

- `.env` and environment-specific `.env.*` files; `.env.example` is kept
- `.git`, `.venv`, `venv`, `node_modules`, Flutter/Gradle build caches
- local SQLite/database files and downloads
- Android signing files and local machine properties
- Python bytecode and test caches

The ZIP is created outside the project root and does not include itself. This is the preferred way to share the project for the next audit. Do not include live API keys in screenshots, logs, or source bundles.

## Verification

Build-environment checks for this patch:

```text
Python suite: 83 tests
Failures: 0
Errors: 0
RuntimeWarning: none
Python bytecode compilation: passed
Source bundle exclusion tests: passed
```

Flutter files were not changed in Patch 5. Existing Flutter verification remains the result from the developer machine; rerun `flutter analyze` and `flutter test` only if local source conflicts occurred while applying this backend patch.

## Apply on Windows

1. Close the backend process.
2. Back up `C:\stiker-dev`.
3. Extract this patch ZIP and merge the contents of `stiker-dev/` into `C:\stiker-dev`, replacing matching files.
4. Run:

```powershell
cd C:\stiker-dev
python -m compileall backend scripts tests
python scripts/run_tests.py
```

Expected: 83 tests, 0 failures, 0 errors, and no unawaited-coroutine warnings.

5. Create a safe source bundle when sharing the next project snapshot:

```powershell
python scripts/create_source_bundle.py
```

## Credential incident found in the supplied snapshot

The uploaded project ZIP contained a non-empty `SCRAPECREATORS_API_KEY` in `.env`. The same credential value was also present as a hard-coded value in `backend/extractor_adapter.py` in two Git commits included in that ZIP. The key value is intentionally not reproduced here.

Treat that credential as compromised:

1. Revoke the old key in the ScrapeCreators dashboard immediately.
2. Generate a replacement key and store it only in the local `.env` / deployment secret manager.
3. Do not put the replacement key in source code, Git, screenshots, logs, or ZIPs.
4. Before sharing the Git repository again, rewrite the affected Git history (after taking a backup) and coordinate a force-push with anyone using that repository. Deleting `.env` or editing the current file alone does not remove a credential from old commits.

The source-bundle script in Patch 5 excludes `.env` and `.git`, but it cannot revoke credentials or clean the remote GitHub history for you.

## Configuration boundary

`EXTRACTION_PROVIDER` remains controlled only by the backend environment. No paid provider is auto-enabled by this patch. Do not paste the `.env` file or its values into a shared ZIP. Rotate any provider key included in an uploaded archive.

## What this patch does not do

- It does not add an independent TikTok scraper.
- It does not make the provider-free `disabled` extraction route return stickers.
- It does not add login/authentication or distributed rate limiting to the public media proxy. Those remain release-hardening tasks before broad unauthenticated public exposure.
- It does not alter Flutter or WhatsApp export behavior.
