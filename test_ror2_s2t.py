"""ror2_s2t.py 模組翻譯功能的測試。

執行：uv run --with pytest --with "OpenCC>=1.1.9" pytest
"""
import json
from pathlib import Path

import ror2_s2t

SKILL = {"SKILL_NAME": {"en": "Chain Slash", "zh-TW": "鎖鏈斬"}}


def write_mod(mods_dir: Path, name: str, loader: str, strings: dict, version: str = "1.0.0") -> None:
    mods_dir.mkdir(exist_ok=True)
    content = {"mod": name, "version": version, "loader": loader, "strings": strings}
    (mods_dir / f"{name}.json").write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")


def add_plugin(profile: Path, name: str, version: str = "1.0.0") -> None:
    plugin = profile / "BepInEx" / "plugins" / name
    plugin.mkdir(parents=True)
    (plugin / "manifest.json").write_text(json.dumps({"version_number": version}), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_install_writes_r2api_mod_as_language_file_keyed_by_language(tmp_path):
    write_mod(tmp_path / "mods", "Author-Survivor", "r2api", SKILL)
    add_plugin(tmp_path / "profile", "Author-Survivor")

    ok = ror2_s2t.install_mods(tmp_path / "mods", tmp_path / "profile", tmp_path / "zh-TW", "zh-TW")

    written = tmp_path / "profile" / "BepInEx" / "plugins" / "RoR2_zh-TW" / "Author-Survivor.language"
    assert read_json(written) == {"zh-TW": {"SKILL_NAME": "鎖鏈斬"}}
    assert ok


def test_install_writes_language_folder_mod_into_game_language_folder(tmp_path):
    write_mod(tmp_path / "mods", "Author-Hud", "language-folder", SKILL)
    add_plugin(tmp_path / "profile", "Author-Hud")
    (tmp_path / "zh-TW").mkdir()

    ror2_s2t.install_mods(tmp_path / "mods", tmp_path / "profile", tmp_path / "zh-TW", "zh-TW")

    assert read_json(tmp_path / "zh-TW" / "mod_Author-Hud.json") == {"strings": {"SKILL_NAME": "鎖鏈斬"}}
    assert not (tmp_path / "profile" / "BepInEx" / "plugins" / "RoR2_zh-TW").exists()


def test_install_skips_mod_that_is_not_in_the_profile(tmp_path):
    write_mod(tmp_path / "mods", "Author-Survivor", "r2api", SKILL)
    add_plugin(tmp_path / "profile", "Someone-Else")

    ok = ror2_s2t.install_mods(tmp_path / "mods", tmp_path / "profile", tmp_path / "zh-TW", "zh-TW")

    assert not (tmp_path / "profile" / "BepInEx" / "plugins" / "RoR2_zh-TW").exists()
    assert ok


def test_install_leaves_out_strings_without_a_translation(tmp_path):
    strings = {**SKILL, "SKILL_DESCRIPTION": {"en": "Whip forward."}}
    write_mod(tmp_path / "mods", "Author-Survivor", "r2api", strings)
    add_plugin(tmp_path / "profile", "Author-Survivor")

    ror2_s2t.install_mods(tmp_path / "mods", tmp_path / "profile", tmp_path / "zh-TW", "zh-TW")

    written = tmp_path / "profile" / "BepInEx" / "plugins" / "RoR2_zh-TW" / "Author-Survivor.language"
    assert read_json(written) == {"zh-TW": {"SKILL_NAME": "鎖鏈斬"}}


def test_install_refuses_translation_whose_markup_differs_from_the_source(tmp_path):
    strings = {"SKILL_DESCRIPTION": {"en": "Deal <style=cIsDamage>220%</style>.", "zh-TW": "造成<style=cIsDamage>220%。"}}
    write_mod(tmp_path / "mods", "Author-Survivor", "r2api", strings)
    add_plugin(tmp_path / "profile", "Author-Survivor")

    ok = ror2_s2t.install_mods(tmp_path / "mods", tmp_path / "profile", tmp_path / "zh-TW", "zh-TW")

    assert not (tmp_path / "profile" / "BepInEx" / "plugins" / "RoR2_zh-TW").exists()
    assert not ok


def test_install_warns_when_installed_mod_version_differs(tmp_path, capsys):
    write_mod(tmp_path / "mods", "Author-Survivor", "r2api", SKILL, version="1.0.2")
    add_plugin(tmp_path / "profile", "Author-Survivor", version="1.1.0")

    ok = ror2_s2t.install_mods(tmp_path / "mods", tmp_path / "profile", tmp_path / "zh-TW", "zh-TW")

    output = capsys.readouterr().out
    assert "1.0.2" in output and "1.1.0" in output
    assert (tmp_path / "profile" / "BepInEx" / "plugins" / "RoR2_zh-TW" / "Author-Survivor.language").is_file()
    assert ok


def test_markup_diff_accepts_tags_in_a_different_order():
    source = "<style=cIsDamage>Stunning</style>. Deal {0}% damage."
    translated = "造成{0}%傷害。<style=cIsDamage>眩暈</style>。"

    assert ror2_s2t.markup_diff(source, translated) == []


def test_markup_diff_reports_a_dropped_closing_tag():
    source = "Gain <style=cIsUtility>armor</style>."
    translated = "獲得<style=cIsUtility>護甲。"

    assert ror2_s2t.markup_diff(source, translated) == ["-</style>"]


def test_markup_diff_reports_a_changed_placeholder():
    assert ror2_s2t.markup_diff("Lasts {0}s.", "持續{1}秒。") == ["+{1}", "-{0}"]


def test_find_profile_resolves_a_profile_name(tmp_path):
    add_plugin(tmp_path / "profiles" / "Purist", "Author-Survivor")

    assert ror2_s2t.find_profile("Purist", tmp_path / "profiles") == tmp_path / "profiles" / "Purist"


def test_find_profile_accepts_a_full_path(tmp_path):
    add_plugin(tmp_path / "elsewhere", "Author-Survivor")

    assert ror2_s2t.find_profile(str(tmp_path / "elsewhere"), tmp_path / "profiles") == tmp_path / "elsewhere"


def test_find_profile_returns_none_for_an_unknown_profile(tmp_path):
    add_plugin(tmp_path / "profiles" / "Purist", "Author-Survivor")

    assert ror2_s2t.find_profile("Typo", tmp_path / "profiles") is None


def test_stale_files_reports_file_that_no_longer_exists_in_the_source(tmp_path):
    for folder, names in (("zh-CN", ["Items.json"]), ("zh-TW", ["Items.json", "Removed.json"])):
        (tmp_path / folder).mkdir()
        for name in names:
            (tmp_path / folder / name).write_text("{}", encoding="utf-8")

    assert ror2_s2t.stale_files(tmp_path / "zh-CN", tmp_path / "zh-TW") == [Path("Removed.json")]


def test_stale_files_ignores_installed_mod_translations(tmp_path):
    (tmp_path / "zh-CN").mkdir()
    (tmp_path / "zh-TW").mkdir()
    (tmp_path / "zh-TW" / "mod_Author-Hud.json").write_text("{}", encoding="utf-8")

    assert ror2_s2t.stale_files(tmp_path / "zh-CN", tmp_path / "zh-TW") == []
