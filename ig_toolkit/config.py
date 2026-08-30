"""環境変数・パス設定の読み込み。"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("IGTOOL_DATA_DIR", BASE_DIR / "data")).resolve()
POSTS_DIR = DATA_DIR / "posts"
EXPORTS_DIR = DATA_DIR / "exports"

NG_WORDS_PATH = Path(
    os.environ.get("IGTOOL_NG_WORDS_PATH", BASE_DIR / "config" / "ng_words.txt")
).resolve()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("IGTOOL_CLAUDE_MODEL", "claude-sonnet-5")


def ensure_dirs() -> None:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
