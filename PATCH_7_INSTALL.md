# StickerDrop Patch 7 — Installation

Patch 7 adds an offline qualification gate for future authorized extraction sources. It does not enable a TikTok scraper or change provider selection.

## Apply

1. Back up the project folder.
2. Extract this ZIP into the StickerDrop project root (`C:\stiker-dev`).
3. Allow the supplied `backend`, `scripts`, `tests`, and `docs` paths to merge. Replace `README.md` with the included updated copy.
4. Do not overwrite `.env`, Railway variables, Android signing files, or the deployed configuration.
5. Keep `EXTRACTION_PROVIDER=disabled`.

## Verify

```powershell
cd C:\stiker-dev
python -m compileall -q backend scripts tests
python -W error::RuntimeWarning scripts/run_tests.py
```

Expected result:

```text
Tests run: 98
Failures: 0
Errors: 0
ALL TESTS PASSED SUCCESSFULLY.
```

## Qualify an authorized source capture

Place a normalized JSON comment response and the exact downloaded WebP bytes in local files. Do not commit signed CDN URLs, tokens, cookies, or private payloads.

```powershell
python scripts/qualify_adapter_source.py `
  --fixture .\source-response.json `
  --comment-id 7700946321838818056 `
  --media-file .\sticker.webp `
  --expected-sha256 b39c96a52d3ce821d0f48c8fb590e25404ca6758a8fbffe11737b867b9cca878
```

Exit code `0` and status `qualified` mean all source/media checks passed. Exit code `2` means the data is incomplete or failed a check. `metadata_only` is not a pass.

This is an offline verifier. It does not fetch the fixture URL or contact TikTok/provider services. Full source integration remains a separate step after authorization and live acceptance testing.
