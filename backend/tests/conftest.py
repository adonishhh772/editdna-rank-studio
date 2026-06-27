import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_file.name}"
os.environ["DEMO_MODE"] = ""

from app.config import get_settings

get_settings.cache_clear()

from app.db import init_db

init_db()
