"""環境変数・パス設定の読み込み。"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("IGTOOL_DATA_DIR", BASE_DIR / "data")).resolve()
POSTS_DIR = DATA_DIR / "posts"
EXPORTS_DIR = DATA_DIR / "exports"

# キャプション自動生成に使うClaude Code CLIのコマンド名(PATH上にあるもの)
CLAUDE_CLI_COMMAND = os.environ.get("IGTOOL_CLAUDE_CLI_COMMAND", "claude")
CLAUDE_CLI_TIMEOUT = float(os.environ.get("IGTOOL_CLAUDE_CLI_TIMEOUT", "180"))


def ensure_dirs() -> None:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
