"""
settings_manager.py
パッド設定（ファイルパス・キー割り当て・音量）を JSON で保存・復元する
"""

import json
import os
from typing import Any


DEFAULT_KEYS = [
    "q", "w", "e", "r",
    "a", "s", "d", "f",
    "z", "x", "c", "v",
    "1", "2", "3", "4",
]

DEFAULT_SETTINGS_PATH = os.path.join(
    os.path.expanduser("~"), "Documents", "MPCSampler", "settings.json"
)


class SettingsManager:
    """
    アプリ設定を JSON ファイルに保存・復元するクラス。
    保存先: ~/Documents/MPCSampler/settings.json
    """

    def __init__(self, path: str = DEFAULT_SETTINGS_PATH):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    # ------------------------------------------------------------------
    # デフォルト設定生成
    # ------------------------------------------------------------------
    def default_settings(self, num_pads: int = 16) -> dict[str, Any]:
        pads = []
        for i in range(num_pads):
            pads.append({
                "index": i,
                "file_path": "",
                "key": DEFAULT_KEYS[i] if i < len(DEFAULT_KEYS) else "",
                "volume": 0.8,
                "label": f"PAD {i + 1:02d}",
            })
        return {
            "version": 1,
            "master_volume": 1.0,
            "pads": pads,
        }

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------
    def save(self, settings: dict[str, Any]) -> bool:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[SettingsManager] save error: {e}")
            return False

    # ------------------------------------------------------------------
    # 読み込み
    # ------------------------------------------------------------------
    def load(self, num_pads: int = 16) -> dict[str, Any]:
        if not os.path.isfile(self.path):
            return self.default_settings(num_pads)
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # バージョン互換チェック・不足フィールド補完
            data = self._migrate(data, num_pads)
            return data
        except Exception as e:
            print(f"[SettingsManager] load error: {e}")
            return self.default_settings(num_pads)

    def _migrate(self, data: dict, num_pads: int) -> dict:
        """古いバージョンの設定ファイルを現在の形式に変換する"""
        defaults = self.default_settings(num_pads)
        # pads リストの長さを揃える
        pads = data.get("pads", [])
        while len(pads) < num_pads:
            idx = len(pads)
            pads.append(defaults["pads"][idx])
        data["pads"] = pads[:num_pads]
        # マスター音量
        if "master_volume" not in data:
            data["master_volume"] = 1.0
        # 各パッドの不足フィールド補完
        for i, pad in enumerate(data["pads"]):
            default_pad = defaults["pads"][i]
            for key, val in default_pad.items():
                if key not in pad:
                    pad[key] = val
        return data

    def get_settings_path(self) -> str:
        return self.path
