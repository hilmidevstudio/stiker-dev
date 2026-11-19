"""
Test script to start uvicorn in a subprocess, hit the API endpoints, and shut down cleanly.
Uses httpx with trust_env=False to bypass local sandbox proxy.
"""

import subprocess
import time
import json
import httpx
import sys

def main():
    print("=" * 70)
    print("STICKERDROP FASTAPI LIVE SERVER TEST")
    print("=" * 70)
    print("Starting uvicorn server on http://127.0.0.1:8000 ...")

    proc = subprocess.Popen(
        [r".venv\Scripts\python.exe", "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    time.sleep(2.0)
    try:
        with httpx.Client(trust_env=False, timeout=10.0) as client:
            # Test 1: GET /health
            print("1. Testing GET /health ...")
            resp = client.get("http://127.0.0.1:8000/health")
            assert resp.status_code == 200
            print("   -> Status:", resp.status_code, resp.json())

            # Test 2: POST /v1/resolve-and-extract
            print("2. Testing POST /v1/resolve-and-extract ...")
            payload = {
                "url": "https://www.tiktok.com/@nyariprompt/video/7708356144804236564?share_comment_id=7708394712596972308",
                "provider": "mock"
            }
            resp2 = client.post("http://127.0.0.1:8000/v1/resolve-and-extract", json=payload)
            assert resp2.status_code == 200
            data2 = resp2.json()
            print(f"   -> Status: {resp2.status_code}")
            print(f"   -> Video ID:    {data2.get('video_id')}")
            print(f"   -> Comment ID:  {data2.get('comment_id')}")
            print(f"   -> Author:      @{data2.get('author', {}).get('unique_id')}")
            print(f"   -> Sticker ID:  {data2.get('sticker', {}).get('sticker_id')}")
            print(f"   -> Format:      {data2.get('sticker', {}).get('format')}")
            print(f"   -> Media URL:   {data2.get('sticker', {}).get('media_url')}")

            # Test 3: GET /v1/resolve-and-extract
            print("3. Testing GET /v1/resolve-and-extract ...")
            resp3 = client.get(
                "http://127.0.0.1:8000/v1/resolve-and-extract",
                params={
                    "url": "https://www.tiktok.com/@nyariprompt/video/7708356144804236564?share_comment_id=7708394712596972308",
                    "provider": "mock"
                }
            )
            assert resp3.status_code == 200
            data3 = resp3.json()
            print(f"   -> Status: {resp3.status_code}")
            print(f"   -> Success: {data3.get('success')}")

        print("\n" + "=" * 70)
        print("ALL FASTAPI SERVER ENDPOINTS TESTED SUCCESSFULLY!")
        print("=" * 70)
        return 0
    except Exception as e:
        print(f"\n[X] Live test failed: {e}")
        return 1
    finally:
        proc.terminate()
        proc.wait(timeout=3)
        print("Server process terminated cleanly.")

if __name__ == "__main__":
    sys.exit(main())
