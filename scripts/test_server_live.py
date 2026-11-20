"""Safe local FastAPI smoke test.

Checks only /health and /v1/extraction-status. It does not send a TikTok link,
call an extraction provider, invoke a mock sticker, or download media.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-access-log",
    ]
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        deadline = time.monotonic() + 15.0
        with httpx.Client(timeout=2.0, trust_env=False, follow_redirects=False) as client:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    print("FAILED: LOCAL_BACKEND_EXITED_EARLY")
                    return 1
                try:
                    health = client.get(f"{base_url}/health")
                    if health.status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.2)
            else:
                print("FAILED: LOCAL_BACKEND_START_TIMEOUT")
                return 1

            health_data = health.json()
            if health_data.get("status") != "ok":
                print("FAILED: HEALTH_RESPONSE_INVALID")
                return 1

            status_response = client.get(f"{base_url}/v1/extraction-status")
            if status_response.status_code != 200:
                print(f"FAILED: EXTRACTION_STATUS_HTTP_{status_response.status_code}")
                return 1
            provider_status = status_response.json()
            if provider_status.get("provider_called") is not False:
                print("FAILED: STATUS_ENDPOINT_CALLED_PROVIDER")
                return 1

            print("LOCAL BACKEND SMOKE TEST: PASSED")
            print(f"Health: {health_data.get('status')}")
            print(f"Configured provider: {provider_status.get('provider')}")
            print(f"Provider called: {provider_status.get('provider_called')}")
            print("No TikTok, source-service, or paid-provider request was made.")
            return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
