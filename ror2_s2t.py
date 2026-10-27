# /// script
# requires-python = ">=3.9"
# dependencies = ["OpenCC>=1.1.9"]
# ///
"""Risk of Rain 2：把內建的簡體中文語言資料夾 (zh-CN) 轉成繁體中文 (zh-TW)。

用法：
    uv run ror2_s2t.py                              # 自動尋找 Steam 或 Epic 上的遊戲
    uv run ror2_s2t.py --game-dir "D:\\Games\\Risk of Rain 2"
    uv run ror2_s2t.py --zip RoR2_zh-TW.zip          # 另外打包成 zip 分享給別人
    uv run ror2_s2t.py --profile Purist_v4           # 模組翻譯只裝進這個 r2modman 設定檔

模組翻譯（mods 資料夾）預設會裝進 r2modman 的每一個設定檔，沒裝對應模組的設定檔會略過。

遊戲更新後重跑一次即可；之後在遊戲的語言選單選「繁體中文」。
"""
from __future__ import annotations

import argparse
import codecs
import json
import os
import re
import shutil
import sys
import zipfile
from collections import Counter
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
# 譯文必須原樣保留的標記：<style=...> 這類標籤與 {0} 佔位符
MARKUP = re.compile(r"<[^<>]*>|\{\d+[^{}]*\}")

# 模組的英文文字沒有簡體來源可轉，譯文是人工翻的，一個模組一個檔案放在這裡
MODS_DIR = Path(__file__).resolve().parent / "mods"
PROFILES_DIR = (
    Path(os.environ.get("APPDATA", "")) / "r2modmanPlus-local" / "RiskOfRain2" / "profiles"
)
MOD_TEXT = "zh-TW"  # 模組翻譯檔裡譯文的鍵名
# R2API 會讀取 plugins 底下所有 *.language 檔，我們的檔案集中放在這個資料夾
MOD_PLUGIN_DIR = "RoR2_zh-TW"
MOD_FILE_PREFIX = "mod_"  # 放進遊戲語言資料夾的模組翻譯檔名開頭
# 模組寫死在程式裡的文字（mods 檔案的 literals）由這個 BepInEx 外掛在遊戲裡替換，原始碼在 plugin 資料夾
PLUGIN_DLL = Path(__file__).resolve().parent / "plugin" / "RoR2_zh-TW.HardcodedText.dll"
LITERALS_SUFFIX = ".literals"  # 外掛讀取的翻譯表副檔名

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


def steam_install_dirs() -> list[Path]:
    """Steam 每個收藏庫裡這款遊戲會在的位置。"""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam = Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except (ImportError, OSError):
        return []

    libraries = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        text = vdf.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            libraries.append(Path(match.group(1).replace("\\\\", "\\")))
    return [library / "steamapps" / "common" / APP_DIR for library in libraries]


def epic_install_dirs(program_data: Path) -> list[Path]:
    """Epic Games Launcher 記錄的安裝位置，每款裝好的遊戲一個；r2modman 找 Epic 版也是讀這個檔案。"""
    record = program_data / "Epic" / "UnrealEngineLauncher" / "LauncherInstalled.dat"
    try:
        installs = json.loads(record.read_text(encoding="utf-8-sig"))["InstallationList"]
        return [Path(install["InstallLocation"]) for install in installs]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def find_game_dir() -> Path | None:
    program_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
    for game in [*steam_install_dirs(), *epic_install_dirs(program_data)]:
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


def markup_diff(source: str, translated: str) -> list[str]:
    """回傳譯文比原文少（-）或多（+）的標籤與佔位符；翻譯會調動語序，所以不比較順序。"""
    before = Counter(MARKUP.findall(source))
    after = Counter(MARKUP.findall(translated))
    return sorted(
        [f"-{mark}" for mark in (before - after).elements()]
        + [f"+{mark}" for mark in (after - before).elements()]
    )


def find_profile(name: str, profiles_dir: Path) -> Path | None:
    """name 可以是 r2modman 的設定檔名稱，或設定檔資料夾的完整路徑。"""
    for candidate in (Path(name), profiles_dir / name):
        if (candidate / "BepInEx" / "plugins").is_dir():
            return candidate
    return None


def find_profiles(profiles_dir: Path) -> list[Path]:
    """回傳 r2modman 的所有設定檔。r2modman 沒有把目前選用的設定檔記在讀得到的地方，所以全部都算。"""
    if not profiles_dir.is_dir():
        return []
    return sorted(p for p in profiles_dir.iterdir() if (p / "BepInEx" / "plugins").is_dir())


def stale_files(source_dir: Path, target_dir: Path) -> list[Path]:
    """回傳輸出資料夾裡來源已經沒有的檔案；我們自己裝進去的模組翻譯不算。"""
    return sorted(
        relative
        for relative in (p.relative_to(target_dir) for p in target_dir.rglob("*") if p.is_file())
        if not (source_dir / relative).exists() and not relative.name.startswith(MOD_FILE_PREFIX)
    )


def escape_literal(text: str) -> str:
    """翻譯表一行一條、以 tab 分隔原文與譯文，所以要跳脫反斜線、tab 和換行；開頭的 @ 是指令，也要跳脫。"""
    escaped = text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")
    return "\\" + escaped if escaped.startswith("@") else escaped


def format_literals(
    assembly: str,
    literals: dict[str, dict[str, str]],
    language: str,
    refresh: list[str] = (),
    walk: list[str] = (),
) -> str:
    """寫成外掛讀的翻譯表；literals 是 {類別名稱: {英文: 譯文}}，譯文是空字串的略過。

    refresh 是切換語言後要請模組重算文字的靜態方法（「命名空間.類別::方法」）。
    walk 是要直接從靜態欄位往下找字串的類別，用在模組啟動時就把文字存進資料的情況。
    """
    lines = [f"@language {language}", f"@assembly {assembly}"] + [f"@refresh {method}" for method in refresh]
    lines += [f"@walk {type_name}" for type_name in walk]
    for type_name, entries in literals.items():
        lines.append(f"@type {type_name}")
        lines += [f"{escape_literal(en)}\t{escape_literal(text)}" for en, text in entries.items() if text]
    return "\n".join(lines) + "\n"


def install_mods(
    mods_dir: Path, profile_dir: Path, target_dir: Path, language: str, plugin_dll: Path = PLUGIN_DLL
) -> bool:
    """把模組翻譯裝進模組設定檔；設定檔沒裝的模組會略過。有譯文未通過檢查時回傳 False。"""
    plugins = profile_dir / "BepInEx" / "plugins"
    ok = True
    needs_plugin = False
    for path in sorted(mods_dir.glob("*.json")):
        mod = json.loads(path.read_text(encoding="utf-8"))
        name = mod["mod"]
        if not (plugins / name).is_dir():
            print(f"  {name}: 設定檔沒有安裝這個模組，略過")
            continue

        strings = {
            token: entry[MOD_TEXT] for token, entry in mod["strings"].items() if entry.get(MOD_TEXT)
        }
        literals = mod.get("literals", {})
        broken = False
        for token, text in strings.items():
            diff = markup_diff(mod["strings"][token]["en"], text)
            if diff:
                print(f"  {name}: {token} 的標籤或佔位符與原文不一致 {diff}")
                broken = True
        for entries in literals.values():
            for en, text in entries.items():
                diff = markup_diff(en, text) if text else []
                if diff:
                    print(f"  {name}: 寫死的文字「{en[:30]}」的標籤或佔位符與原文不一致 {diff}")
                    broken = True
        if broken:
            print(f"  {name}: 未安裝")
            ok = False
            continue

        manifest = plugins / name / "manifest.json"
        if manifest.is_file():
            installed = json.loads(manifest.read_text(encoding="utf-8-sig")).get("version_number")
            if installed != mod["version"]:
                print(f"  {name}: 注意：翻譯依 {mod['version']} 版製作，安裝的是 {installed} 版，可能有缺漏")

        if mod["loader"] == "r2api":
            # R2API 裡語言專屬的字串優先於模組寫死的英文，頂層的鍵就是語言名稱
            output, root = plugins / MOD_PLUGIN_DIR / f"{name}.language", language
        else:
            # 模組直接查遊戲語言資料夾載入的內容（例如 LookingGlass），不經過 R2API
            output, root = target_dir / f"{MOD_FILE_PREFIX}{name}.json", "strings"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps({root: strings}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"  {name}: 已安裝 {len(strings)} 條翻譯 -> {output}")

        count = sum(1 for entries in literals.values() for text in entries.values() if text)
        if count:
            table = plugins / MOD_PLUGIN_DIR / f"{name}{LITERALS_SUFFIX}"
            table.parent.mkdir(parents=True, exist_ok=True)
            table.write_bytes(
                format_literals(
                    mod["assembly"], literals, language, mod.get("refresh", []), mod.get("walk", [])
                ).encode("utf-8")
            )
            print(f"  {name}: 已安裝 {count} 條寫死文字的翻譯 -> {table}")
            needs_plugin = True

    if needs_plugin:
        if plugin_dll.is_file():
            shutil.copyfile(plugin_dll, plugins / MOD_PLUGIN_DIR / plugin_dll.name)
            print(f"  已安裝替換寫死文字的外掛 -> {plugins / MOD_PLUGIN_DIR / plugin_dll.name}")
        else:
            print(f"  找不到外掛 {plugin_dll}，寫死的文字不會被翻譯")
            ok = False
    return ok


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
    parser.add_argument(
        "--profile", metavar="設定檔", help="只把模組翻譯裝進這個 r2modman 設定檔（名稱或路徑）；預設裝進所有設定檔"
    )
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
    if args.profile:
        profile = find_profile(args.profile, PROFILES_DIR)
        if profile is None:
            print(f"找不到模組設定檔：{args.profile}（在 {PROFILES_DIR} 底下也沒有）")
            return 1
        profiles = [profile]
    else:
        profiles = find_profiles(PROFILES_DIR)

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

    for relative in stale_files(source_dir, target_dir):
        print(f"  注意：{relative} 在來源已不存在，可能是舊版遺留的檔案")

    if not profiles:
        print("沒有找到 r2modman 設定檔，未安裝模組翻譯。")
    for profile in profiles:
        print(f"模組翻譯 -> {profile}")
        if not install_mods(MODS_DIR, profile, target_dir, args.target):
            failed = True

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
