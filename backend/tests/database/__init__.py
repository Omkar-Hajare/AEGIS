import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
database_dir = os.path.join(backend_dir, "database")
if database_dir not in __path__:
    __path__.append(database_dir)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)
