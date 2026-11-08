"""tools 底下 Python 工具共用的路徑。

- REPO：repo 根目錄（tools 的上一層）。
- WORK：工具的輸出資料夾，預設 tools/work（已被 .gitignore 排除），可用環境變數 ROR2_TOOLS_WORK 改到別處。
- CACHE／PROFILES：r2modman 的快取與設定檔資料夾。
- profile()：設定檔名稱沒給就讀環境變數 ROR2_PROFILE。
- game_dir()：遊戲資料夾，環境變數 ROR2_GAME 優先，否則借用 ror2_s2t 的尋找邏輯（需要 OpenCC）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
WORK = Path(os.environ.get("ROR2_TOOLS_WORK") or TOOLS / "work")
R2MM = Path(os.environ.get("APPDATA", "")) / "r2modmanPlus-local" / "RiskOfRain2"
CACHE = R2MM / "cache"
PROFILES = R2MM / "profiles"
MODS = REPO / "mods"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def work(*parts: str) -> Path:
    """WORK 底下的資料夾，不存在就建立。"""
    path = WORK.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def profile(name: str | None = None) -> Path:
    """r2modman 設定檔資料夾；name 可以是名稱或完整路徑。"""
    name = name or os.environ.get("ROR2_PROFILE")
    if not name:
        names = sorted(p.name for p in PROFILES.iterdir() if (p / "BepInEx").is_dir()) if PROFILES.is_dir() else []
        raise SystemExit(f"請用 --profile 或環境變數 ROR2_PROFILE 指定設定檔，可選：{', '.join(names)}")
    for candidate in (Path(name), PROFILES / name):
        if (candidate / "BepInEx" / "plugins").is_dir():
            return candidate
    raise SystemExit(f"找不到設定檔：{name}")


def game_dir() -> Path:
    """遊戲安裝資料夾（裡面有 Risk of Rain 2_Data）。"""
    if os.environ.get("ROR2_GAME"):
        return Path(os.environ["ROR2_GAME"])
    import ror2_s2t

    game = ror2_s2t.find_game_dir()
    if game is None:
        raise SystemExit("找不到遊戲資料夾，請用環境變數 ROR2_GAME 指定")
    return game


def mod_file(mod: str) -> Path:
    """mods/<mod>.json；mod 可以只寫名稱的一部分，但要只對到一個檔案。"""
    exact = MODS / f"{mod}.json"
    if exact.is_file():
        return exact
    hits = [p for p in MODS.glob("*.json") if mod.lower() in p.stem.lower()]
    if len(hits) != 1:
        raise SystemExit(f"mods 裡對到 {len(hits)} 個檔案：{mod}")
    return hits[0]
