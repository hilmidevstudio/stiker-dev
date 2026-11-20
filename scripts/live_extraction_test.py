"""Deprecated safe wrapper for the former direct paid-provider test harness.

Use `scripts/live_source_acceptance.py` instead. This compatibility entry point
never instantiates ScrapeCreators/ScrapeSocial adapters and never calls a paid API.
"""

from __future__ import annotations

import sys
from live_source_acceptance import main


if __name__ == "__main__":
    print(
        "The legacy direct-provider live test has been retired. "
        "This command now delegates to the authorized-source acceptance test."
    )
    sys.exit(main())
