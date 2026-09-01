"""igtool-gui: ブラウザで操作できるローカルWebアプリ(Flask)。

ターミナル操作の代わりにGUIで下書き作成・画像トリミング・キャプション入力・
投稿前チェック・スケジュール管理を行えるようにする。
"""

from __future__ import annotations

import os
import threading
import webbrowser

from flask import Flask

from .. import config


def create_app() -> Flask:
    config.ensure_dirs()
    app = Flask(__name__)
    app.secret_key = os.environ.get("IGTOOL_WEB_SECRET", "igtool-local-dev-secret-key")
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB(画像アップロード用)

    from . import routes

    app.register_blueprint(routes.bp)
    return app


def main() -> None:
    """`igtool-gui` コマンドのエントリーポイント。ローカルサーバーを起動しブラウザを開く。"""
    app = create_app()
    port = int(os.environ.get("IGTOOL_WEB_PORT", "5000"))
    url = f"http://127.0.0.1:{port}"
    print(f"igtool GUI を起動しました: {url}  (終了するには Ctrl+C)")

    def _open_browser() -> None:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    if not os.environ.get("IGTOOL_WEB_NO_BROWSER"):
        threading.Timer(1.0, _open_browser).start()

    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
