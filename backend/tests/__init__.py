import os
import sys

# Ensure backend root directory is on sys.path for test runners executing `python -m unittest discover -s tests`
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
