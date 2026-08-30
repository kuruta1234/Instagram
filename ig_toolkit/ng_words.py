"""NGワード(薬機法・景表法・差別表現などの要注意語)チェック。"""

from __future__ import annotations

from pathlib import Path

from . import config


def load_ng_words(path: Path | None = None) -> list[str]:
    path = path or config.NG_WORDS_PATH
    if not path.exists():
        return []
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.append(line)
    return words


def check_text(text: str, ng_words: list[str] | None = None) -> list[str]:
    """textに含まれるNGワードの一覧を返す(空リストなら問題なし)。"""
    ng_words = ng_words if ng_words is not None else load_ng_words()
    return [word for word in ng_words if word and word in text]
