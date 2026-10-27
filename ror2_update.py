# /// script
# requires-python = ">=3.11"
# ///
"""先從 GitHub 更新安裝包裡的翻譯檔案，再執行 ror2_s2t.py 安裝；安裝包的「安裝.bat」執行的就是這個腳本。

用法（參數會原樣交給 ror2_s2t.py）：
    python ror2_update.py --profile Purist_v5
    python ror2_update.py --no-update          # 不連 GitHub，直接用現有的檔案安裝

只用標準函式庫：安裝包裡的 Python 拿掉了 pip，也不會把腳本所在的資料夾加進 sys.path。
連不上 GitHub、下載的檔案不完整，或新版的 ror2_s2t.py 需要不同的 Python 套件時，都不更新，照樣用現有的檔案安裝。
"""
from __future__ import annotations

import http.client
import re
import subprocess
import sys
import tomllib
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath

REPO = "csimsong1/Risk_of_Rain_2_zh-TW"
BRANCH = "main"
ARCHIVE_URL = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"
# 自動更新做不到時（例如要裝新的套件），請朋友到這裡下載整個安裝包
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
TIMEOUT = 20

BUNDLE_DIR = Path(__file__).resolve().parent
SCRIPT = "ror2_s2t.py"
# 安裝包裡除了 Python 以外的內容，make_bundle.py 也照這兩個清單打包。
# FILES 在 GitHub 上找不到時保留原本的；DIRS 整個換成 GitHub 上的內容，repo 刪掉的翻譯這裡也會刪掉
FILES = (SCRIPT, "ror2_update.py", "plugin/RoR2_zh-TW.HardcodedText.dll")
DIRS = ("mods", "overrides")
NO_UPDATE = "--no-update"

# update() 的結果
UPDATED, CURRENT, SKIPPED, OFFLINE, INVALID, OUTDATED, FAILED = (
    "updated", "current", "skipped", "offline", "invalid", "outdated", "failed"
)


def script_metadata(text: str) -> dict:
    """讀出腳本開頭 PEP 723 區塊的內容（相依套件、Python 版本），沒有這個區塊就是空的。"""
    match = re.search(
        r"(?m)^# /// script$\s(?P<content>(^#(| .*)$\s)+)^# ///$", text.replace("\r\n", "\n")
    )
    if not match:
        return {}
    content = "".join(line[2:] or "\n" for line in match["content"].splitlines(keepends=True))
    return tomllib.loads(content)


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "RoR2_zh-TW-updater"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def bundle_path(name: str) -> str | None:
    """壓縮檔裡的路徑（去掉最上層的「repo-分支」資料夾）屬於安裝包的話，回傳它在安裝包裡的路徑。"""
    parts = PurePosixPath(name).parts[1:]
    if not parts or name.endswith("/") or ".." in parts:
        return None
    relative = "/".join(parts)
    if relative in FILES or (len(parts) > 1 and parts[0] in DIRS):
        return relative
    return None


def read_archive(data: bytes) -> dict[str, bytes]:
    """從 GitHub 的分支壓縮檔取出安裝包用得到的檔案；不是壓縮檔或缺了轉換腳本時丟出 ValueError。"""
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            files = {}
            for name in archive.namelist():
                relative = bundle_path(name)
                if relative:
                    files[relative] = archive.read(name)
    except zipfile.BadZipFile as error:
        raise ValueError(error) from error
    if SCRIPT not in files:
        raise ValueError(f"壓縮檔裡沒有 {SCRIPT}")
    return files


def same_content(path: Path, data: bytes) -> bool:
    # 安裝包的文字檔是從 Windows 的工作目錄複製的（CRLF），GitHub 給的是 LF，換行不同不算有變
    return path.is_file() and path.read_bytes().replace(b"\r\n", b"\n") == data.replace(b"\r\n", b"\n")


def update(bundle: Path) -> str:
    """把 bundle 裡的翻譯檔案換成 GitHub 上的最新版本，回傳結果（UPDATED、CURRENT 等）。"""
    if (bundle / ".git").exists():
        print("這裡是開發用的 git repo，不從 GitHub 更新。")
        return SKIPPED
    print("檢查 GitHub 上的翻譯更新...", flush=True)
    try:
        data = download(ARCHIVE_URL)
    except (OSError, http.client.HTTPException) as error:
        print(f"連不上 GitHub（{error}），這次用目前的翻譯安裝。")
        return OFFLINE
    try:
        files = read_archive(data)
        remote = script_metadata(files[SCRIPT].decode("utf-8"))
    except ValueError as error:
        print(f"從 GitHub 下載的檔案不完整（{error}），這次用目前的翻譯安裝。")
        return INVALID
    local_script = bundle / SCRIPT
    local = script_metadata(local_script.read_text(encoding="utf-8")) if local_script.is_file() else {}
    if remote != local:
        # 安裝包裡的 Python 沒有 pip，裝不了新的套件，只能換一整個新的安裝包
        print("GitHub 上的新版需要不同的 Python 套件，無法自動更新，這次用目前的翻譯安裝。")
        return OUTDATED

    changed = [name for name, data in files.items() if not same_content(bundle / name, data)]
    removed = [
        path
        for name in DIRS
        if (bundle / name).is_dir()
        for path in (bundle / name).rglob("*")
        if path.is_file() and path.relative_to(bundle).as_posix() not in files
    ]
    if not changed and not removed:
        print("翻譯已經是最新版本。")
        return CURRENT
    try:
        for name in changed:
            (bundle / name).parent.mkdir(parents=True, exist_ok=True)
            (bundle / name).write_bytes(files[name])
        for path in removed:
            path.unlink()
    except OSError as error:
        print(f"有檔案無法更新（{error}），請關掉開著安裝包資料夾裡檔案的程式，再執行一次。")
        return FAILED
    print(f"已從 GitHub 更新翻譯：更新 {len(changed)} 個檔案，移除 {len(removed)} 個檔案。")
    return UPDATED


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(errors="backslashreplace")
    args = sys.argv[1:] if argv is None else argv

    status = SKIPPED
    if NO_UPDATE in args:
        args = [arg for arg in args if arg != NO_UPDATE]
    else:
        try:
            status = update(BUNDLE_DIR)
        except Exception as error:  # 更新程式本身出錯，也不能讓朋友裝不了翻譯
            print(f"更新時發生錯誤（{error!r}），這次用目前的翻譯安裝。")
            status = FAILED
        print()
    sys.stdout.flush()
    # 用另一個行程執行，才會跑到剛更新的 ror2_s2t.py
    exit_code = subprocess.run([sys.executable, str(BUNDLE_DIR / SCRIPT), *args], cwd=BUNDLE_DIR).returncode
    if status == OUTDATED:
        print()
        print(f"這份安裝包太舊，無法自動更新到最新的翻譯。請到 {RELEASES_URL} 下載新的安裝包，")
        print("解壓縮後執行裡面的「安裝.bat」。")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
