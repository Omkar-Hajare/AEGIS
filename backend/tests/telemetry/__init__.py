import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
telemetry_dir = os.path.join(backend_dir, "telemetry")
if telemetry_dir not in __path__:
    __path__.append(telemetry_dir)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)
