# /// script
# requires-python = ">=3.9"
# dependencies = ["OpenCC>=1.1.9"]
# ///
"""在暫存資料夾模擬 install_mods，不碰真實的設定檔和遊戲資料夾。

用法：simulate.py [--profile 名稱] [資料夾]

照設定檔的 plugins 結構建一份假的（只複製資料夾名稱和 manifest.json，所以版本提醒也會出現），
再把 repo 的 mods 裝進去。資料夾預設 work/sim，每次都會清空重建。
設定檔沒給就讀環境變數 ROR2_PROFILE。有 markup_diff 錯誤時結束碼是 1。
"""
import argparse
import shutil
import sys
from pathlib import Path

import _paths
import ror2_s2t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", help="r2modman 設定檔名稱或資料夾（預設讀 ROR2_PROFILE）")
    ap.add_argument("folder", nargs="?", default=str(_paths.WORK / "sim"))
    args = ap.parse_args()

    src = _paths.profile(args.profile) / "BepInEx" / "plugins"
    sim = Path(args.folder)
    if sim.exists():
        shutil.rmtree(sim)
    plugins = sim / "profile" / "BepInEx" / "plugins"
    for d in src.iterdir():
        if d.is_dir():
            (plugins / d.name).mkdir(parents=True)
            if (d / "manifest.json").exists():
                shutil.copy(d / "manifest.json", plugins / d.name / "manifest.json")
    (sim / "zh-TW").mkdir()
    ok = ror2_s2t.install_mods(_paths.MODS, sim / "profile", sim / "zh-TW", "zh-TW")
    print("ok =", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
