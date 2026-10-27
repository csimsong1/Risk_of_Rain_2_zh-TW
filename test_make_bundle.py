"""make_bundle.py 的測試。

執行：uv run --with pytest --with "OpenCC>=1.1.9" pytest
"""
import codecs
import subprocess
import zipfile
from pathlib import Path

import pytest

import make_bundle
import ror2_update

HEADER = '# /// script\n# requires-python = ">=3.9"\n# dependencies = ["OpenCC>=1.1.9"]\n# ///\n'
PYTHON_FILES = (
    "python.exe",
    "python313._pth",
    "get-pip.py",
    "Scripts/pip.exe",
    "Lib/site-packages/pip/__init__.py",
    "Lib/site-packages/pip-25.3.dist-info/METADATA",
)


def touch(root: Path, *relatives: str) -> None:
    for relative in relatives:
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_bytes(b"")


def make_python(root: Path) -> Path:
    """假的 Python embeddable package，只有打包流程會碰到的檔案。"""
    touch(root, *PYTHON_FILES)
    return root


def make_project(root: Path) -> Path:
    touch(
        root,
        "ror2_update.py",
        "mods/Author-Survivor.json",
        "overrides/icon.png",
        "plugin/RoR2_zh-TW.HardcodedText.dll",
        "plugin/HardcodedText.cs",
    )
    (root / "ror2_s2t.py").write_text(HEADER + "print('hi')\n", encoding="utf-8")
    return root


class FakeRun:
    """代替 subprocess.run：記下指令，並模擬 7-Zip 解壓縮與 pip 安裝套件的結果。"""

    def __init__(self):
        self.commands = []
        self.failing = None

    def __call__(self, command, **options):
        self.commands.append((command, options))
        if self.failing and self.failing in command:
            return subprocess.CompletedProcess(command, 1)
        if command[1] == "x":
            make_python(Path(command[3][2:]) / "python_embeded")
        if "pip" in command:
            touch(Path(command[0]).parent, "Lib/site-packages/opencc/__init__.py")
        return subprocess.CompletedProcess(command, 0)


@pytest.fixture
def run(monkeypatch):
    fake = FakeRun()
    monkeypatch.setattr(make_bundle.subprocess, "run", fake)
    return fake


def build(tmp_path: Path, source: Path | None = None) -> tuple[bool, Path]:
    zip_path = tmp_path / "bundle.zip"
    source = source or make_python(tmp_path / "python_embeded")
    return make_bundle.build(source, make_project(tmp_path / "project"), zip_path), zip_path


def names(zip_path: Path) -> set[str]:
    with zipfile.ZipFile(zip_path) as archive:
        return set(archive.namelist())


def read(zip_path: Path, name: str) -> bytes:
    with zipfile.ZipFile(zip_path) as archive:
        return archive.read(name)


def test_script_dependencies_come_from_the_inline_metadata_block(tmp_path):
    script = tmp_path / "script.py"
    script.write_text(HEADER + "import opencc\n", encoding="utf-8")

    assert make_bundle.script_dependencies(script) == ["OpenCC>=1.1.9"]


def test_script_without_inline_metadata_has_no_dependencies(tmp_path):
    script = tmp_path / "script.py"
    script.write_text("print('hi')\n", encoding="utf-8")

    assert make_bundle.script_dependencies(script) == []


def test_find_python_dir_accepts_the_folder_that_holds_python_exe(tmp_path):
    touch(tmp_path, "python.exe")

    assert make_bundle.find_python_dir(tmp_path) == tmp_path


def test_find_python_dir_looks_one_level_down(tmp_path):
    touch(tmp_path, "python_embeded/python.exe", "notes/readme.txt")

    assert make_bundle.find_python_dir(tmp_path) == tmp_path / "python_embeded"


def test_find_python_dir_is_none_without_python_exe(tmp_path):
    touch(tmp_path, "notes/readme.txt")

    assert make_bundle.find_python_dir(tmp_path) is None


def test_prune_removes_install_tools_and_keeps_other_packages(tmp_path):
    make_python(tmp_path)
    touch(
        tmp_path,
        "Lib/site-packages/setuptools/__init__.py",
        "Lib/site-packages/setuptools-80.9.0.dist-info/METADATA",
        "Lib/site-packages/_distutils_hack/__init__.py",
        "Lib/site-packages/distutils-precedence.pth",
        "Lib/site-packages/opencc/__init__.py",
        "Lib/site-packages/opencc-1.4.2.dist-info/METADATA",
    )

    make_bundle.prune(tmp_path)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["Lib", "python.exe", "python313._pth"]
    assert sorted(p.name for p in (tmp_path / "Lib" / "site-packages").iterdir()) == [
        "opencc",
        "opencc-1.4.2.dist-info",
    ]


def test_build_packs_python_script_and_translations_under_one_folder(tmp_path, run):
    ok, zip_path = build(tmp_path)

    assert ok
    assert names(zip_path) == {
        "RoR2_zh-TW/安裝.bat",
        "RoR2_zh-TW/說明.txt",
        "RoR2_zh-TW/ror2_s2t.py",
        "RoR2_zh-TW/ror2_update.py",
        "RoR2_zh-TW/mods/Author-Survivor.json",
        "RoR2_zh-TW/overrides/icon.png",
        "RoR2_zh-TW/plugin/RoR2_zh-TW.HardcodedText.dll",
        "RoR2_zh-TW/python_embeded/python.exe",
        "RoR2_zh-TW/python_embeded/python313._pth",
        "RoR2_zh-TW/python_embeded/Lib/site-packages/opencc/__init__.py",
    }


def test_build_installs_the_script_dependencies_then_runs_the_updater_offline_with_the_bundled_python(tmp_path, run):
    build(tmp_path)

    (install, _), (check, check_options) = run.commands
    python = Path(install[0])
    assert python.name == "python.exe" and python.parent.name == "python_embeded"
    assert install[1:4] == ["-m", "pip", "install"] and install[-1] == "OpenCC>=1.1.9"
    assert check == [str(python), "ror2_update.py", "--no-update", "--help"]
    assert Path(check_options["cwd"]) == python.parent.parent


def test_build_leaves_the_python_it_was_given_untouched(tmp_path, run):
    source = make_python(tmp_path / "python_embeded")

    build(tmp_path, source)

    assert sorted(p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()) == sorted(PYTHON_FILES)


def test_build_leaves_out_bytecode_caches(tmp_path, run):
    source = make_python(tmp_path / "python_embeded")
    touch(source, "Lib/site-packages/__pycache__/cached.pyc")

    _, zip_path = build(tmp_path, source)

    assert not [name for name in names(zip_path) if "__pycache__" in name]


def test_launcher_is_a_batch_file_cmd_can_read(tmp_path, run):
    _, zip_path = build(tmp_path)

    launcher = read(zip_path, "RoR2_zh-TW/安裝.bat")
    # cmd 讀不懂 BOM，第一行指令會失效；換行要是 CRLF
    assert not launcher.startswith(codecs.BOM_UTF8)
    assert b"\n" not in launcher.replace(b"\r\n", b"")
    assert "python_embeded\\python.exe ror2_update.py %*" in launcher.decode("utf-8").splitlines()


def test_guide_opens_as_utf8_in_notepad(tmp_path, run):
    _, zip_path = build(tmp_path)

    guide = read(zip_path, "RoR2_zh-TW/說明.txt")
    assert guide.startswith(codecs.BOM_UTF8)
    assert "安裝.bat" in guide.decode("utf-8-sig")
    assert ror2_update.RELEASES_URL in guide.decode("utf-8-sig")


def test_build_extracts_an_archive_with_7zip(tmp_path, run, monkeypatch):
    monkeypatch.setattr(make_bundle, "find_7z", lambda: Path("7z.exe"))
    archive = tmp_path / "python_embeded_v3.13.15.7z"
    archive.write_bytes(b"")

    ok, zip_path = build(tmp_path, archive)

    extract = run.commands[0][0]
    assert extract[:3] == ["7z.exe", "x", str(archive)] and extract[3].startswith("-o")
    assert ok
    assert "RoR2_zh-TW/python_embeded/python.exe" in names(zip_path)


def test_build_refuses_an_archive_when_7zip_is_missing(tmp_path, run, monkeypatch, capsys):
    monkeypatch.setattr(make_bundle, "find_7z", lambda: None)
    archive = tmp_path / "python_embeded_v3.13.15.7z"
    archive.write_bytes(b"")

    ok, zip_path = build(tmp_path, archive)

    assert not ok and not zip_path.exists()
    assert "7-Zip" in capsys.readouterr().out
    assert run.commands == []


def test_build_refuses_a_folder_without_python(tmp_path, run, capsys):
    (tmp_path / "empty").mkdir()

    ok, zip_path = build(tmp_path, tmp_path / "empty")

    assert not ok and not zip_path.exists()
    assert "python.exe" in capsys.readouterr().out
    assert run.commands == []


def test_build_stops_when_the_dependencies_cannot_be_installed(tmp_path, run, capsys):
    run.failing = "pip"

    ok, zip_path = build(tmp_path)

    assert not ok and not zip_path.exists()
    assert "pip" in capsys.readouterr().out
    assert len(run.commands) == 1


def test_build_refuses_a_project_whose_plugin_is_not_built(tmp_path, run, capsys):
    project = make_project(tmp_path / "project")
    (project / "plugin" / "RoR2_zh-TW.HardcodedText.dll").unlink()

    ok = make_bundle.build(make_python(tmp_path / "python_embeded"), project, tmp_path / "bundle.zip")

    assert not ok and not (tmp_path / "bundle.zip").exists()
    assert "dotnet build" in capsys.readouterr().out


def test_build_writes_no_bundle_when_the_bundled_python_cannot_run_the_script(tmp_path, run, capsys):
    run.failing = "--help"

    ok, zip_path = build(tmp_path)

    assert not ok and not zip_path.exists()
    assert "未產生安裝包" in capsys.readouterr().out
    assert len(run.commands) == 2


def run_main(tmp_path: Path, monkeypatch, source: Path) -> int:
    monkeypatch.setattr(make_bundle, "PROJECT_DIR", make_project(tmp_path / "project"))
    monkeypatch.setattr("sys.argv", ["make_bundle.py", str(source), "--output", str(tmp_path / "out.zip")])
    return make_bundle.main()


def test_main_writes_the_bundle_to_the_output_path(tmp_path, run, monkeypatch, capsys):
    exit_code = run_main(tmp_path, monkeypatch, make_python(tmp_path / "python_embeded"))

    assert exit_code == 0
    assert "RoR2_zh-TW/ror2_s2t.py" in names(tmp_path / "out.zip")
    assert "out.zip" in capsys.readouterr().out


def test_main_reports_a_python_path_that_does_not_exist(tmp_path, run, monkeypatch, capsys):
    exit_code = run_main(tmp_path, monkeypatch, tmp_path / "missing")

    assert exit_code == 1
    assert "missing" in capsys.readouterr().out
    assert not (tmp_path / "out.zip").exists()
