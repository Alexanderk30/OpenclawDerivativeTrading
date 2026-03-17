#!/usr/bin/env python3
"""Live trading runner - USE WITH EXTREME CAUTION."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("⚠️  LIVE TRADING MODE ⚠️")
print("Real money will be at risk!")
print("Ensure you have:")
print("  1. Set PAPER_TRADING=false in .env")
print("  2. Updated ALPACA_BASE_URL to live endpoint")
print("  3. Tested extensively in paper mode")
print()

confirm = input("Type 'LIVE' to confirm: ")
if confirm != "LIVE":
    print("Cancelled. Exiting.")
    sys.exit(0)

from src.main import main

if __name__ == "__main__":
    sys.argv.extend(["--mode", "live"])
    main()
