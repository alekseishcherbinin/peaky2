"""`python -m mascope_assign ...` -> the same CLI as the `mascope-assign` script."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
