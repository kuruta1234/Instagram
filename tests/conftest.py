import importlib
import sys

import pytest


@pytest.fixture()
def isolated_data_dir(tmp_path, monkeypatch):
    """各テストごとに独立したdata/ディレクトリを使わせる。"""
    monkeypatch.setenv("IGTOOL_DATA_DIR", str(tmp_path / "data"))

    # config, storage は import 時に環境変数を読むため再読み込みする
    for mod_name in ["ig_toolkit.config", "ig_toolkit.storage"]:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
        else:
            importlib.import_module(mod_name)

    from ig_toolkit import config

    config.ensure_dirs()
    yield tmp_path
