"""Main entry point for project execution and terminal demonstration.

Run directly via:
    python main.py
or
    python main.py --step-by-step
"""

import sys
from pathlib import Path

# Ensure root directory is in sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo_prototype import main

if __name__ == "__main__":
    main()
