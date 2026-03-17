#!/usr/bin/env python3
"""Paper trading runner."""
import sys

sys.path.insert(0, "/Users/clawd/OpenclawDerivativeTrading")

from src.main import main

if __name__ == "__main__":
    import sys
    sys.argv.extend(["--mode", "paper"])
    main()
