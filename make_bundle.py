# /// script
# requires-python = ">=3.11"
# ///
"""把轉換腳本、模組翻譯和可攜式 Python 打包成安裝包，朋友解壓縮後點兩下就能安裝。

用法：
    uv run make_bundle.py "D:\\python_embeded_v3.13.15.7z"
    uv run make_bundle.py "D:\\python_embeded" --output RoR2_zh-TW_安裝包.zip

需要一份裝好 pip 的 Python embeddable package：資料夾，或 7-Zip 能解開的壓縮檔。
打包時會用它的 pip 安裝轉換腳本需要的套件，所以要能連上網路；原本那份不會被更動。
"""
from __future__ import annotations

import argparse
import codecs
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SCRIPT = "ror2_s2t.py"
DATA_DIRS = ("mods", "overrides")
DEFAULT_OUTPUT = "RoR2_zh-TW_安裝包.zip"
BUNDLE_NAME = "RoR2_zh-TW"  # 壓縮檔裡最上層的資料夾，解壓縮後不會散成一堆檔案
PYTHON_DIR = "python_embeded"
LAUNCHER = "安裝.bat"
GUIDE = "說明.txt"
# 朋友只需要執行腳本，這些安裝工具不用帶
INSTALL_TOOLS = ("pip", "setuptools", "wheel", "pkg_resources", "_distutils_hack")

# 存成沒有 BOM 的 UTF-8：cmd 讀不懂 BOM，中文要等 chcp 65001 之後才讀得對
LAUNCHER_TEXT = f"""\
@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "{PYTHON_DIR}\\python.exe" (
    echo 找不到 {PYTHON_DIR}，請先把整個壓縮檔解壓縮，再執行解壓縮出來的「{LAUNCHER}」。
    echo.
    pause
    exit /b 1
)
{PYTHON_DIR}\\python.exe {SCRIPT} %*
echo.
pause
"""

GUIDE_TEXT = f"""\
Risk of Rain 2 繁體中文語言包（含模組翻譯）

安裝
  1. 把整個壓縮檔解壓縮，不要在壓縮檔裡直接執行。
  2. 點兩下「{LAUNCHER}」。Windows 跳出安全性警告的話，選擇仍要執行。
  3. 開遊戲（已經開著就重開），在主選單右上角的國旗選單拉到最下面，選「繁體中文」。

遊戲或模組更新之後，再點一次「{LAUNCHER}」就好。

它做了什麼
  - 把遊戲內建的簡體中文轉成繁體中文，放進遊戲的
    Risk of Rain 2_Data\\StreamingAssets\\Language\\zh-TW 資料夾。
  - 把模組的繁體中文翻譯放進 r2modman 每個設定檔的
    BepInEx\\plugins\\RoR2_zh-TW 資料夾；設定檔沒有安裝的模組會略過。

找不到遊戲或設定檔
  遊戲不是用 Steam 或 Epic Games 安裝，或 r2modman 的資料不在預設位置時，要自己指定路徑。
  在這個資料夾的網址列輸入 cmd 按 Enter，再執行（路徑換成自己的）：
      {LAUNCHER} --game-dir "D:\\Games\\Risk of Rain 2"
      {LAUNCHER} --profile "D:\\r2modman\\RiskOfRain2\\profiles\\設定檔名稱"

移除
  先把遊戲語言切回別的，再刪掉上面提到的兩個資料夾。
"""


def script_dependencies(script: Path) -> list[str]:
    """讀出腳本開頭 PEP 723 區塊宣告的相依套件，安裝包裡的 Python 要裝一樣的東西。"""
    match = re.search(
        r"(?m)^# /// script$\s(?P<content>(^#(| .*)$\s)+)^# ///$", script.read_text(encoding="utf-8")
    )
    if not match:
        return []
    content = "".join(line[2:] or "\n" for line in match["content"].splitlines(keepends=True))
    return tomllib.loads(content).get("dependencies", [])


def find_7z() -> Path | None:
    found = shutil.which("7z")
    if found:
        return Path(found)
    for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if root and (Path(root) / "7-Zip" / "7z.exe").is_file():
            return Path(root) / "7-Zip" / "7z.exe"
    return None


def find_python_dir(root: Path) -> Path | None:
    """回傳放 python.exe 的資料夾：root 本身，或它底下唯一有 python.exe 的子資料夾。"""
    if (root / "python.exe").is_file():
        return root
    found = [path for path in root.iterdir() if (path / "python.exe").is_file()]
    return found[0] if len(found) == 1 else None


def prune(python_dir: Path) -> None:
    """刪掉執行腳本用不到的安裝工具（pip、setuptools 等），縮小安裝包。"""
    site_packages = python_dir / "Lib" / "site-packages"
    # distutils-precedence.pth 會在啟動時載入 _distutils_hack，要跟著一起刪
    unneeded = [python_dir / "Scripts", python_dir / "get-pip.py", site_packages / "distutils-precedence.pth"]
    for tool in INSTALL_TOOLS:
        unneeded += [site_packages / tool, *site_packages.glob(f"{tool}-*.dist-info")]
    for path in unneeded:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()


def write_zip(bundle: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in bundle.rglob("*") if p.is_file()):
            if "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(bundle.parent).as_posix())


def build(source: Path, project_dir: Path, zip_path: Path) -> bool:
    """組出安裝包並壓縮成 zip；source 不會被更動。失敗時回傳 False，不會留下壓縮檔。"""
    with tempfile.TemporaryDirectory() as temp:
        unpacked = source
        if not source.is_dir():
            seven_zip = find_7z()
            if seven_zip is None:
                print("找不到 7-Zip，無法解開壓縮檔。請先自行解壓縮，改用資料夾路徑。")
                return False
            unpacked = Path(temp) / "unpacked"
            extract = [str(seven_zip), "x", str(source), f"-o{unpacked}", "-y"]
            if subprocess.run(extract, stdout=subprocess.DEVNULL).returncode != 0:
                print(f"解壓縮失敗：{source}")
                return False
        found = find_python_dir(unpacked)
        if found is None:
            print(f"在 {source} 裡找不到 python.exe，請確認這是 Python embeddable package。")
            return False

        bundle = Path(temp) / BUNDLE_NAME
        python_dir = bundle / PYTHON_DIR
        shutil.copytree(found, python_dir)
        python = str(python_dir / "python.exe")

        requirements = script_dependencies(project_dir / SCRIPT)
        print(f"安裝 {'、'.join(requirements)} ...", flush=True)
        quiet = ["--disable-pip-version-check", "--no-warn-script-location"]
        install = [python, "-m", "pip", "install", *quiet, *requirements]
        if subprocess.run(install).returncode != 0:
            print("套件安裝失敗。這份 Python 要先裝好 pip，打包時也要能連上網路。")
            return False
        prune(python_dir)

        shutil.copy2(project_dir / SCRIPT, bundle)
        for name in DATA_DIRS:
            shutil.copytree(project_dir / name, bundle / name)
        (bundle / LAUNCHER).write_bytes(LAUNCHER_TEXT.replace("\n", "\r\n").encode("utf-8"))
        # 帶 BOM，舊版記事本才不會把 UTF-8 當成 Big5 開
        (bundle / GUIDE).write_bytes(codecs.BOM_UTF8 + GUIDE_TEXT.replace("\n", "\r\n").encode("utf-8"))

        # 用包好的 Python 實際跑一次，確認拿掉安裝工具之後腳本還能執行
        check = [python, SCRIPT, "--help"]
        if subprocess.run(check, cwd=bundle, stdout=subprocess.DEVNULL).returncode != 0:
            print("包好的 Python 無法執行腳本，未產生安裝包。")
            return False
        write_zip(bundle, zip_path)
    return True


def main() -> int:
    sys.stdout.reconfigure(errors="backslashreplace")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "python",
        type=Path,
        metavar="python_embeded",
        help="裝好 pip 的 Python embeddable package：資料夾，或 7-Zip 能解開的壓縮檔",
    )
    parser.add_argument(
        "--output", type=Path, default=Path(DEFAULT_OUTPUT), metavar="檔案", help=f"輸出的壓縮檔（預設 {DEFAULT_OUTPUT}）"
    )
    args = parser.parse_args()

    if not args.python.exists():
        print(f"找不到：{args.python}")
        return 1
    if not build(args.python, PROJECT_DIR, args.output):
        return 1
    megabytes = args.output.stat().st_size / 1024 / 1024
    print(f"已打包：{args.output}（{megabytes:.1f} MB）")
    print(f"朋友把它解壓縮後，點兩下「{LAUNCHER}」即可安裝。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
