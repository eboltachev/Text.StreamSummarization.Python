import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root / "src"))
sys.path.insert(0, str(project_root))

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback when python-dotenv is absent
    def load_dotenv(*_args, **_kwargs):
        return False


load_dotenv()

authorization = "Authorization" if not os.environ.get("DEBUG") else "user_id"
