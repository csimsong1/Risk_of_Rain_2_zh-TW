# /// script
# requires-python = ">=3.9"
# dependencies = ["OpenCC>=1.1.9"]
# ///
"""Risk of Rain 2：把內建的簡體中文語言資料夾 (zh-CN) 轉成繁體中文 (zh-TW)。

用法：
    uv run ror2_s2t.py                              # 自動尋找 Steam 上的遊戲
    uv run ror2_s2t.py --game-dir "D:\\Games\\Risk of Rain 2"
    uv run ror2_s2t.py --zip RoR2_zh-TW.zip          # 另外打包成 zip 分享給別人

遊戲更新後重跑一次即可；之後在遊戲的語言選單選「繁體中文」。
"""
from __future__ import annotations

import argparse
import codecs
import re
import shutil
import sys
import zipfile
from pathlib import Path

import opencc

APP_DIR = "Risk of Rain 2"
LANG_SUBDIR = Path("Risk of Rain 2_Data") / "StreamingAssets" / "Language"
TEXT_SUFFIXES = {".json", ".txt"}
# 放在這個資料夾的檔案（例如 icon.png 國旗圖示）會取代來源語言的同名檔案
OVERRIDES_DIR = Path(__file__).resolve().parent / "overrides"
HAN = re.compile(
    "[\u2e80-\u2fdf\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0003ffff]"
)

# 大陸用語 -> 臺灣用語，套用在已轉成繁體字的文字上（較長的詞優先）。
# 不用 OpenCC 內建的 s2twp 詞庫，因為它在遊戲文本會誤轉，
# 例如「的士兵」->「計程車兵」、「呼出」->「撥出」、「擴展包」->「擴充套件包」。
TERMS: dict[str, str] = {
    "鼠標": "滑鼠",
    "屏幕": "螢幕",
    "全屏": "全螢幕",
    "窗口": "視窗",
    "菜單": "選單",
    "分辨率": "解析度",
    "刷新率": "更新率",
    "圖標": "圖示",
    "界面": "介面",
    "用戶": "使用者",
    "默認": "預設",
    "設置": "設定",
    "設置一面": "設置一面",  # 「設置一面屏障」是放置的意思，維持原樣
    '"視頻"': '"視訊"',  # 設定分頁名稱
    "視頻": "影片",
    "音頻": "音訊",
    "服務器": "伺服器",
    "網絡": "網路",
    "局域網": "區域網路",
    "帶寬": "頻寬",
    "在線": "線上",
    "鏈接": "連結",
    "登錄": "登入",
    "加載": "載入",
    "存儲": "儲存",
    "搜索": "搜尋",
    "創建": "建立",
    "交互": "互動",
    "激活": "啟用",
    "禁用": "停用",
    "幾率": "機率",
    "概率": "機率",
    "信息素": "費洛蒙",
    "信息": "資訊",
    "聊天消息": "聊天訊息",
    "輸入消息": "輸入訊息",
    "系統消息": "系統訊息",
    "信號": "訊號",
    "通信": "通訊",
    "數據": "資料",
    "內存": "記憶體",
    "軟件": "軟體",
    "硬件": "硬體",
    "模塊": "模組",
    "芯片": "晶片",
    "傳感器": "感測器",
    "掃描儀": "掃描器",
    "打印機": "印表機",
    "打印": "列印",
    "複印機": "影印機",
    "性能": "效能",
    "兼容": "相容",
    "優化": "最佳化",
    "算法": "演算法",
    "字符串": "字串",
    "密鑰": "金鑰",
    "內置": "內建",
    "剪貼板": "剪貼簿",
    "剪切板": "剪貼簿",
    "擴展包": "擴充包",
    "擴展內容": "擴充內容",
    "加入社區": "加入社群",
    "環境光屏蔽": "環境光遮蔽",
    "激光": "雷射",
    "納米": "奈米",
    "超聲波": "超音波",
    "人工智能": "人工智慧",
    "筆記本電腦": "筆記型電腦",
    "意大利": "義大利",
    "新西蘭": "紐西蘭",
    "賬": "帳",
    "粘": "黏",
}
TERMS_PATTERN = re.compile(
    "|".join(re.escape(term) for term in sorted(TERMS, key=len, reverse=True))
)

# 一簡對多繁轉錯的地方：{轉換後的錯誤寫法（正規表示式）: 正確寫法}
FIXES: dict[str, str] = {
    # 只 / 隻：數字後面當量詞用的「只」（排除「只有、只是、只能…」）
    r"(?<=\d)只(?![有是能要會需剩對在為])": "隻",
    "幾十只這種生物": "幾十隻這種生物",
    "大多隻是": "大多只是",
    # 並 / 併：只有「合併、併入」這類詞才用「併」
    r"(?<![合兼吞歸])併(?!入|吞|購|攏|發症)": "並",
    # 發 / 髮
    "仿生髮電站": "仿生發電站",
    "不斷髮": "不斷發",
    "明白髮生": "明白發生",
    # 幹 / 乾
    "正事要乾的": "正事要幹的",
    "無人機乾的事": "無人機幹的事",
    "乾硬體的": "幹硬體的",
    "快乾掉": "快幹掉",
    # 面 / 麵
    "塊麵板": "塊面板",
    "塊麵具": "塊面具",
    # 製 / 制
    "氣體制造": "氣體製造",
    "被複制": "被複製",
    "石制構造": "石製構造",
    "板材壓制": "板材壓製",
    # 後 / 后
    "東西后": "東西後",
    "星球后": "星球後",
    # 衝 / 沖
    "對沖突": "對衝突",
    "通過沖刺": "通過衝刺",
    # 歷 / 曆
    "舊曆歷在目": "舊歷歷在目",
    "水星曆史": "水星歷史",
    # 回 / 迴、復 / 覆
    "回旋鏢": "迴旋鏢",
    "無力迴天": "無力回天",
    "迴歸": "回歸",
    "回覆效果": "回復效果",
    ">回覆<": ">回復<",
    # 其他
    "尤克里裡": "尤克里里",
    "孢子云": "孢子雲",
    "古董鍾": "古董鐘",
    "中游玩": "中遊玩",
    "高几率": "高機率",
    "不準用": "不准用",
    "維恩託": "維恩托",
}
FIX_PATTERNS = [(re.compile(wrong), right) for wrong, right in FIXES.items()]


def find_game_dir() -> Path | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam = Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except (ImportError, OSError):
        return None

    libraries = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        text = vdf.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            libraries.append(Path(match.group(1).replace("\\\\", "\\")))

    for library in libraries:
        game = library / "steamapps" / "common" / APP_DIR
        if (game / LANG_SUBDIR).is_dir():
            return game
    return None


def read_text(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    has_bom = raw.startswith(codecs.BOM_UTF8)
    if has_bom:
        raw = raw[len(codecs.BOM_UTF8):]
    return raw.decode("utf-8"), has_bom


def write_text(path: Path, text: str, has_bom: bool) -> None:
    path.write_bytes((codecs.BOM_UTF8 if has_bom else b"") + text.encode("utf-8"))


def convert(converter: opencc.OpenCC, text: str) -> str:
    converted = converter.convert(text)
    converted = TERMS_PATTERN.sub(lambda match: TERMS[match.group()], converted)
    for wrong, right in FIX_PATTERNS:
        converted = wrong.sub(right, converted)
    return converted


def changed_skeleton_lines(source: str, converted: str) -> list[int]:
    """回傳漢字以外的內容（鍵名、標籤、{0} 佔位符、標點）被改動的行號。"""
    source_lines = source.split("\n")
    converted_lines = converted.split("\n")
    if len(source_lines) != len(converted_lines):
        return [0]
    return [
        number
        for number, (before, after) in enumerate(zip(source_lines, converted_lines), 1)
        if HAN.sub("", before) != HAN.sub("", after)
    ]


def write_zip(game: Path, target_dir: Path, zip_path: Path) -> None:
    """打包語言資料夾；壓縮檔內保留遊戲資料夾底下的路徑，解壓縮到遊戲安裝資料夾即可。"""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in target_dir.rglob("*") if p.is_file()):
            archive.write(path, path.relative_to(game).as_posix())


def set_selfname(text: str, name: str) -> str:
    return re.sub(r'("selfname"\s*:\s*")[^"]*(")', rf"\g<1>{name}\g<2>", text)


def main() -> int:
    sys.stdout.reconfigure(errors="backslashreplace")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game-dir", type=Path, help="遊戲安裝資料夾（預設自動尋找）")
    parser.add_argument("--source", default="zh-CN", help="來源語言資料夾（預設 zh-CN）")
    parser.add_argument("--target", default="zh-TW", help="輸出語言資料夾（預設 zh-TW）")
    parser.add_argument("--name", default="繁體中文", help="語言選單上顯示的名稱")
    parser.add_argument("--zip", type=Path, metavar="檔案", help="另外打包成 zip 方便分享")
    args = parser.parse_args()

    game = args.game_dir or find_game_dir()
    if game is None:
        print("找不到 Risk of Rain 2，請用 --game-dir 指定安裝資料夾。")
        return 1
    source_dir = game / LANG_SUBDIR / args.source
    target_dir = game / LANG_SUBDIR / args.target
    if not source_dir.is_dir():
        print(f"找不到來源語言資料夾：{source_dir}")
        return 1
    if source_dir.resolve() == target_dir.resolve():
        print("來源與輸出不能是同一個資料夾。")
        return 1

    # s2tw：簡體 -> 繁體（臺灣字形），只換字不換詞；用語另由 TERMS 處理
    converter = opencc.OpenCC("s2tw")
    print(f"{source_dir}\n-> {target_dir}")
    failed = False

    for path in sorted(p for p in source_dir.rglob("*") if p.is_file()):
        relative = path.relative_to(source_dir)
        output = target_dir / relative
        output.parent.mkdir(parents=True, exist_ok=True)

        override = OVERRIDES_DIR / relative
        if override.is_file():
            shutil.copyfile(override, output)
            print(f"  {relative}: 已套用 overrides 的自訂檔案")
            continue

        if path.suffix.lower() not in TEXT_SUFFIXES:
            # 圖示等檔案只複製一次，之後自行替換的版本不會被蓋掉
            if output.exists():
                print(f"  {relative}: 已存在，保留")
            else:
                shutil.copyfile(path, output)
                print(f"  {relative}: 已複製")
            continue

        text, has_bom = read_text(path)
        if relative.name == "language.json":
            converted = set_selfname(text, args.name)
        else:
            converted = convert(converter, text)
            # 遊戲的 JSON 不是標準格式，所以只做文字替換，並確認漢字以外完全沒變
            broken = changed_skeleton_lines(text, converted)
            if broken:
                print(f"  {relative}: 轉換動到了漢字以外的內容，未寫入（行號 {broken[:10]}）")
                failed = True
                continue
        write_text(output, converted, has_bom)
        changed = sum(a != b for a, b in zip(text.split("\n"), converted.split("\n")))
        print(f"  {relative}: 已轉換，{changed} 行有變動")

    stale = sorted(
        p.relative_to(target_dir)
        for p in target_dir.rglob("*")
        if p.is_file() and not (source_dir / p.relative_to(target_dir)).exists()
    )
    for relative in stale:
        print(f"  注意：{relative} 在來源已不存在，可能是舊版遺留的檔案")

    if failed:
        print("有檔案未通過檢查，請見上方訊息。")
        return 1
    if args.zip:
        write_zip(game, target_dir, args.zip)
        print(f"已打包：{args.zip}（解壓縮到遊戲安裝資料夾即可安裝）")
    print(f"完成。請在遊戲的語言選單選擇「{args.name}」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
