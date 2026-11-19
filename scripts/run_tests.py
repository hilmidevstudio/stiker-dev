"""
Unified Test Runner for StickerDrop Research & Core System.
"""

import unittest
import sys
import os

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def run_all_tests():
    print("=" * 70)
    print("STICKERDROP SYSTEM TEST SUITE")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=os.path.join(PROJECT_ROOT, "tests"),
        pattern="test_*.py",
        top_level_dir=PROJECT_ROOT
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)

    if result.wasSuccessful():
        print("ALL TESTS PASSED SUCCESSFULLY.")
        return 0
    else:
        print("TEST FAILURES DETECTED.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
