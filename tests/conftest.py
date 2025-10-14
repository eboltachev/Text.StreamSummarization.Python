import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    load_dotenv = None  # type: ignore

if load_dotenv is not None:
    load_dotenv()

authorization = "Authorization" if not os.environ.get("DEBUG") else "user_id"
