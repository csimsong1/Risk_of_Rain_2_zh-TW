"""ror2_update.py 的測試。

執行：uv run --with pytest --with "OpenCC>=1.1.9" pytest
"""
import io
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

import ror2_update

HEADER = '# /// script\n# requires-python = ">=3.9"\n# dependencies = ["OpenCC>=1.1.9"]\n# ///\n'
# GitHub 的分支壓縮檔把所有檔案放在「repo 名稱-分支」資料夾底下
TOP = "Risk_of_Rain_2_zh-TW-main/"
LOCAL = {
    "ror2_s2t.py": HEADER + "print('old')\n",
    "ror2_update.py": "# updater\n",
    "mods/Author-Survivor.json": '{"mod": "old"}',
    "mods/Author-Removed.json": "{}",
    "overrides/icon.png": b"PNG",
    "plugin/RoR2_zh-TW.HardcodedText.dll": b"DLL",
    "python_embeded/python.exe": b"EXE",
    "安裝.bat": "@echo off\r\n",
}
REMOTE = {
    "ror2_s2t.py": HEADER + "print('new')\n",
    "ror2_update.py": "# updater\n",
    "mods/Author-Survivor.json": '{"mod": "new"}',
    "overrides/icon.png": b"PNG",
    "plugin/RoR2_zh-TW.HardcodedText.dll": b"DLL",
    "plugin/HardcodedText.cs": "// source",
    "README.md": "# readme",
    "test_ror2_s2t.py": "",
}


def write(root: Path, files: dict) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            content = content.encode("utf-8")
        path.write_bytes(content)
    return root


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def archive(files: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        zipped.writestr(TOP, "")
        for name, content in files.items():
            zipped.writestr(TOP + name, content)
    return buffer.getvalue()


class FakeGitHub:
    """代替 ror2_update.download：回傳準備好的壓縮檔，或模擬連不上網路。"""

    def __init__(self):
        self.content = archive(REMOTE)
        self.error = None
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        if self.error:
            raise self.error
        return self.content


@pytest.fixture
def github(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(ror2_update, "download", fake)
    return fake


@pytest.fixture
def bundle(tmp_path):
    return write(tmp_path / "RoR2_zh-TW", LOCAL)


def test_update_replaces_changed_files_and_removes_deleted_translations(bundle, github, capsys):
    status = ror2_update.update(bundle)

    assert status == ror2_update.UPDATED
    assert github.urls == [ror2_update.ARCHIVE_URL]
    after = snapshot(bundle)
    assert after["ror2_s2t.py"] == REMOTE["ror2_s2t.py"].encode()
    assert after["mods/Author-Survivor.json"] == b'{"mod": "new"}'
    assert "mods/Author-Removed.json" not in after
    # 只更新安裝包裡原本就有的東西：原始碼、README、測試不會被放進來，Python 和安裝.bat 不會被動到
    assert set(after) == set(LOCAL) - {"mods/Author-Removed.json"}
    assert after["python_embeded/python.exe"] == b"EXE"
    assert "更新 2 個檔案" in capsys.readouterr().out


def test_update_keeps_files_the_archive_does_not_have(bundle, github):
    remote = dict(REMOTE)
    del remote["ror2_update.py"], remote["plugin/RoR2_zh-TW.HardcodedText.dll"]
    github.content = archive(remote)

    assert ror2_update.update(bundle) == ror2_update.UPDATED

    after = snapshot(bundle)
    assert after["ror2_update.py"] == b"# updater\n"
    assert after["plugin/RoR2_zh-TW.HardcodedText.dll"] == b"DLL"


def test_update_reports_nothing_new_when_only_line_endings_differ(tmp_path, github, capsys):
    # 安裝包裡的文字檔是從 Windows 的工作目錄複製的（CRLF），GitHub 給的是 LF
    names = ("ror2_s2t.py", "ror2_update.py", "mods/Author-Survivor.json", "overrides/icon.png", "plugin/RoR2_zh-TW.HardcodedText.dll")
    local = {name: REMOTE[name].replace("\n", "\r\n") if isinstance(REMOTE[name], str) else REMOTE[name] for name in names}
    bundle = write(tmp_path / "RoR2_zh-TW", local)
    before = snapshot(bundle)

    assert ror2_update.update(bundle) == ror2_update.CURRENT

    assert snapshot(bundle) == before
    assert "已經是最新" in capsys.readouterr().out


def test_update_keeps_local_files_when_github_is_unreachable(bundle, github, capsys):
    github.error = urllib.error.URLError("getaddrinfo failed")
    before = snapshot(bundle)

    assert ror2_update.update(bundle) == ror2_update.OFFLINE

    assert snapshot(bundle) == before
    assert "目前的翻譯" in capsys.readouterr().out


@pytest.mark.parametrize(
    "content",
    [b"<html>not a zip</html>", archive({name: c for name, c in REMOTE.items() if name != "ror2_s2t.py"})],
    ids=["not-a-zip", "no-script"],
)
def test_update_keeps_local_files_when_the_download_is_broken(bundle, github, capsys, content):
    github.content = content
    before = snapshot(bundle)

    assert ror2_update.update(bundle) == ror2_update.INVALID

    assert snapshot(bundle) == before
    assert "目前的翻譯" in capsys.readouterr().out


@pytest.mark.parametrize(
    "header",
    [
        HEADER.replace('["OpenCC>=1.1.9"]', '["OpenCC>=1.1.9", "regex"]'),
        HEADER.replace(">=3.9", ">=3.14"),
    ],
    ids=["new-package", "newer-python"],
)
def test_update_keeps_local_files_when_the_script_needs_a_different_python_setup(bundle, github, capsys, header):
    github.content = archive({**REMOTE, "ror2_s2t.py": header + "print('new')\n"})
    before = snapshot(bundle)

    assert ror2_update.update(bundle) == ror2_update.OUTDATED

    assert snapshot(bundle) == before
    assert "目前的翻譯" in capsys.readouterr().out


def test_update_never_writes_outside_the_bundle(bundle, github):
    github.content = archive({**REMOTE, "mods/../../escaped.txt": "x", "mods/../ror2_update.py": "# evil\n"})

    ror2_update.update(bundle)

    assert not (bundle.parent / "escaped.txt").exists()
    assert (bundle / "ror2_update.py").read_text(encoding="utf-8") == "# updater\n"


def test_update_reports_files_it_could_not_replace(bundle, github, capsys):
    # 同名的資料夾擋住了要寫入的檔案
    (bundle / "mods" / "Author-Survivor.json").unlink()
    (bundle / "mods" / "Author-Survivor.json").mkdir()

    assert ror2_update.update(bundle) == ror2_update.FAILED

    assert "無法更新" in capsys.readouterr().out


def test_update_leaves_a_git_checkout_alone(bundle, github):
    (bundle / ".git").mkdir()
    before = snapshot(bundle)

    assert ror2_update.update(bundle) == ror2_update.SKIPPED

    assert github.urls == []
    assert snapshot(bundle) == before


def test_script_metadata_reads_the_inline_block_with_any_line_endings():
    expected = {"requires-python": ">=3.9", "dependencies": ["OpenCC>=1.1.9"]}

    assert ror2_update.script_metadata(HEADER + "print('hi')\n") == expected
    assert ror2_update.script_metadata((HEADER + "print('hi')\n").replace("\n", "\r\n")) == expected
    assert ror2_update.script_metadata("print('hi')\n") == {}


# 假的轉換腳本：印出收到的參數，用指定的結束碼結束
SCRIPT = HEADER + "import sys\nprint('installing', sys.argv[1:])\nsys.exit(int(sys.argv[-1]) if sys.argv[-1].isdigit() else 0)\n"


def run_main(monkeypatch, bundle: Path, *argv: str) -> int:
    monkeypatch.setattr(ror2_update, "BUNDLE_DIR", bundle)
    return ror2_update.main(list(argv))


def test_main_installs_with_the_updated_script_and_passes_the_arguments_on(bundle, github, monkeypatch, capfd):
    github.content = archive({**REMOTE, "ror2_s2t.py": SCRIPT})

    exit_code = run_main(monkeypatch, bundle, "--profile", "Purist_v5")

    assert exit_code == 0
    assert "installing ['--profile', 'Purist_v5']" in capfd.readouterr().out


def test_main_returns_the_exit_code_of_the_install_script(bundle, github, monkeypatch):
    github.content = archive({**REMOTE, "ror2_s2t.py": SCRIPT})

    assert run_main(monkeypatch, bundle, "3") == 3


def test_main_with_no_update_installs_the_local_files_without_asking_github(bundle, github, monkeypatch, capfd):
    write(bundle, {"ror2_s2t.py": SCRIPT})

    run_main(monkeypatch, bundle, ror2_update.NO_UPDATE, "--help")

    assert github.urls == []
    assert "installing ['--help']" in capfd.readouterr().out


def test_main_asks_for_a_new_bundle_after_installing_when_the_script_needs_a_different_python(
    bundle, github, monkeypatch, capfd
):
    write(bundle, {"ror2_s2t.py": SCRIPT})
    github.content = archive({**REMOTE, "ror2_s2t.py": HEADER.replace(">=3.9", ">=3.14")})

    run_main(monkeypatch, bundle)

    out = capfd.readouterr().out
    # 提醒放在安裝的輸出後面，畫面停下來時才看得到
    assert out.index("installing") < out.rindex(ror2_update.RELEASES_URL)


def test_main_still_installs_when_the_update_itself_crashes(bundle, github, monkeypatch, capfd):
    write(bundle, {"ror2_s2t.py": SCRIPT})

    def crash(bundle):
        raise RuntimeError("bug")

    monkeypatch.setattr(ror2_update, "update", crash)

    assert run_main(monkeypatch, bundle) == 0
    out = capfd.readouterr().out
    assert "RuntimeError('bug')" in out and "installing" in out


def test_main_uses_the_python_that_runs_it(bundle, github, monkeypatch, capfd):
    write(bundle, {"ror2_s2t.py": HEADER + "import sys\nprint(sys.executable)\n"})

    run_main(monkeypatch, bundle, ror2_update.NO_UPDATE)

    assert capfd.readouterr().out.strip().splitlines()[-1] == sys.executable
