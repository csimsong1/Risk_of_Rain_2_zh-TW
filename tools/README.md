# 模組文字擷取工具

模組更新時，用這些工具從模組 DLL 重新取得英文、比對新舊版，再套用並檢查譯文。這些工具只給維護翻譯的人用，不會打包進安裝包；`ror2_update.py` 只下載 `FILES`／`DIRS` 列出的檔案，也不會下載這個資料夾。

## 需求

- **Windows PowerShell 5.1**：執行 `.ps1`。錄製器要用 32 位元版（`SysWOW64`），因為 BepInEx.dll 只有 x86 版。請在 PowerShell 裡執行；從 Git Bash 呼叫 `powershell.exe -File` 可能會被執行原則擋下。
- **uv**：執行 Python 工具。需要第三方套件的工具（OpenCC、dnfile、UnityPy）在檔案開頭的 PEP 723 區塊列出套件，`uv run` 會自動安裝。
- **r2modman 快取**：r2modman 會把下載過的每個版本留在 `%APPDATA%\r2modmanPlus-local\RiskOfRain2\cache\<模組>\<版本>\`，比對新舊版要用到。
- **遊戲本體**：錄製器要用 `Managed` 資料夾解析模組的參照，`lookup.py` 要讀官方語言檔。

環境變數都可以不設：

| 變數 | 用途 |
|---|---|
| `ROR2_PROFILE` | r2modman 設定檔名稱或資料夾，`rec.ps1` 和 `simulate.py` 會用到（也可以用參數指定） |
| `ROR2_GAME` | 遊戲資料夾。沒設定時和 `ror2_s2t.py` 一樣，自動在 Steam 和 Epic 裡尋找 |
| `ROR2_TOOLS_WORK` | 輸出資料夾，預設是 `tools\work`（已被 `.gitignore` 排除）。IL 匯出、改寫過的 DLL、錄製結果都放在這裡 |

PowerShell 的設定方式是 `$env:ROR2_PROFILE = 'Purist_v5'`。主控台的編碼是 cp950，從 Bash 管線看 Python 的輸出時，要先設 `PYTHONIOENCODING=utf-8`。

`.ps1` 和 `Rec.cs` 只能用 ASCII：Windows PowerShell 5.1 會把沒有 BOM 的腳本當成 ANSI 字碼頁讀取，中文註解會讓腳本壞掉，所以這兩種檔案的註解用英文。

## 檔案

| 檔案 | 用途 |
|---|---|
| `_common.ps1`、`_paths.py` | 共用的路徑（設定檔、遊戲資料夾、快取、`work`），其他工具都從這裡取得 |
| `ildump.ps1` | 用 Mono.Cecil 把 DLL 的每個方法匯出成文字 IL，一行一個指令；`-Mod` 一次匯出快取裡的兩個版本 |
| `ildiff.py` | 比對同一個模組兩個版本的 IL 匯出（字串、數字常數、方法），以及快取裡的文字檔 |
| `callers.py` | 列出呼叫某個方法的所有方法，用來找出註冊文字的地方 |
| `Rec.cs`、`rec.ps1` | 錄製器：用 Cecil 改寫一份模組 DLL，把註冊文字的呼叫導向記錄器，執行模組的方法，錄下 token 和英文 |
| `compare.py` | 比對錄到的英文和 `mods` 檔的 `en` |
| `lg_buffs.py` | LookingGlass 專用：對 `BuffDefinitions::SetupEnglishDefs` 的 IL 做堆疊求值 |
| `tank/` | Celestial War Tank 專用：`meta.py`（內嵌資源與列舉）、`bundle_dump.py`（用 UnityPy 匯出 prefab）、`interp.py`（IL 直譯器）、`closure.py`（看直譯器還缺哪些外部呼叫） |
| `lookup.py` | 用英文查遊戲官方的 zh-TW 譯名 |
| `apply.py` | 把 `patch.json` 套用到 `mods` 檔，保留原本的 CRLF 和排版 |
| `check.py` | 檢查譯文的標籤、佔位符、用字和空格 |
| `simulate.py` | 在 `work\sim` 模擬安裝，不碰真實的設定檔 |

## 模組更新後的流程

以下指令都在 repo 根目錄執行。例子用 Zabuza；`<舊版>` 是 `mods` 檔 `version` 欄的版本，`<新版>` 是快取裡最新的版本。

### 1. 比對新舊版

```powershell
.\tools\ildump.ps1 -Mod Zerneas-ZabuzaMod
```

```bash
uv run tools/ildiff.py Zabuza
```

`ildump.ps1 -Mod` 預設比 `mods` 檔的版本和快取裡最新的版本（`mods` 檔已經是最新版時，改比前一版），也可以用 `-Old`／`-New` 指定。`ildiff.py` 會列出：

- `+`／`-`：新增或刪除的字串（`ldstr`）；
- `# 數字改變`：數字常數（`ldc.*`）有變動的方法。數字不會出現在字串的差異裡，註冊文字的方法只要有數字改變，就要重新錄製；
- `檔案新增／改變／刪除`：快取裡的 `.json`、`.language`、`.txt` 這類文字檔。

字串和數字都沒有變（只改了程式）的模組，只要更新 `mods` 檔的 `version` 就好。

### 2. 錄製並驗證舊版

先找出註冊文字的方法。Zerneas 系列用自己包裝的 `Modules.Language::Add`，其他模組多半是 `R2API.LanguageAPI::Add`：

```bash
uv run tools/callers.py "tools/work/il/Zerneas-ZabuzaMod@<新版>@ZabuzaMod.dll.il" "\.Modules\.Language::Add\("
```

列出的方法（`AddSpanish` 這類其他語言的除外）就是 `-Call` 要執行的方法。接著在 PowerShell 裡用 32 位元的 PowerShell **先錄舊版**：

```powershell
& "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -File tools\rec.ps1 `
  -ProfileName Purist_v5 `
  -Dll "$env:APPDATA\r2modmanPlus-local\RiskOfRain2\cache\Zerneas-ZabuzaMod\<舊版>\plugins\ZabuzaMod.dll" `
  -Record 'ZabuzaMod\.Modules\.Language::Add\(' `
  -Stub 'Modules\.Content::|ScriptableObject::CreateInstance' `
  -Call 'ZabuzaMod.Survivors.Zabuza.ZabuzaTokens::AddEnglish,ZabuzaMod.Survivors.Zabuza.ZabuzaMastery::Unlockable' `
  -Out tools\work\rec\zabuza-old.json
```

```bash
uv run tools/compare.py Zabuza tools/work/rec/zabuza-old.json
```

- `-Record`：比對被呼叫方法全名的正規表示式。符合的靜態方法（2 或 3 個字串參數）會被換成記錄器。
- `-Stub`：比對 `型別::方法` 的正規表示式。符合的呼叫會丟掉參數、改成推入預設值，用來跳過遊戲外跑不了的呼叫（ScriptableObject、讀取資源、Unity 內部函式）。不需要時整個參數省略，不要傳空字串（PowerShell 5.1 會把空字串參數丟掉）。
- `-Call`／`-Pre`：用逗號分隔的 `型別::方法`，`-Pre` 先執行。參數一律傳 null 或預設值；實例方法會建立一個沒有初始化的物件來呼叫。
- 每個 DLL 都用一個新的 PowerShell 行程錄：同一個行程會沿用已經載入的組件，記錄也會累積下去。

舊版必須完全重現：不同 0、新增 0，「檔案有但沒錄到」只能是直接拿英文當 token 的條目。這樣才能相信新版的結果。接著用同樣的參數錄新版，再用 `compare.py` 比對，看哪些英文不同、新增或消失。某個方法執行失敗時（`FAIL after N`），如果失敗前英文已經錄完（例如 Zerneas 的 `*Tokens::Init` 在 `AddSpanish` 才失敗），就不影響結果。

特殊的模組：

- **LookingGlass**：buff 的文字由 `lg_buffs.py` 從 IL 匯出求值：`uv run tools/lg_buffs.py "tools/work/il/DropPod-LookingGlass@<新版>@LookingGlass.dll.il" tools/work/rec/lg.json`，再用 `compare.py LookingGlass` 比對。
- **Celestial War Tank**：文字來自內嵌 AssetBundle 裡的 prefab，每個版本都要重新抽出：

  ```bash
  W=tools/work/tank/<版本>
  mkdir -p $W
  uv run tools/tank/meta.py "$APPDATA/r2modmanPlus-local/RiskOfRain2/cache/CheeseWithHoles-Celestial_War_Tank/<版本>/TanksMod.dll" $W
  uv run tools/tank/bundle_dump.py $W/res_TanksMod.tanksbundle1 $W/prefabs.json mdlBasicTank mdlBasicXtraTank
  uv run tools/tank/interp.py "tools/work/il/CheeseWithHoles-Celestial_War_Tank@<版本>@TanksMod.dll.il" $W $W/out.json
  uv run tools/compare.py Tank $W/out.json
  ```

  `interp.py` 遇到新版多出來的外部呼叫時會丟出 `NotImplementedError`，用 `closure.py` 看缺了哪些。
- **讀 BepInEx 設定的模組**（Dancer、Pathfinder、Arsonist、Enforcer、Seamstress 這類範本型角色模組）：要先建立 `ConfigFile` 並執行模組讀取設定的方法，錄製器目前沒有這一步。之前的版本把 `BaseUnityPlugin.get_Config` 改寫成回傳一份全新的 `ConfigFile`（也就是預設值），並先呼叫 `BepInEx.Paths.SetExecutablePath` 指到暫存資料夾；遇到這類模組時要補進 `Rec.cs`／`rec.ps1`。
- **寫死在程式裡的文字（`literals`）**：模組更新後，每條英文都要在新版同一個類別的 `ldstr` 裡找得到；大小寫差一個字就翻不到（LookingGlass 1.16.4 把「Per」改成「per」）。`walk` 列出的類別例外，它的文字要在整個 DLL 裡找。

### 3. 翻譯

把要改的內容寫成 `patch.json`（格式見 `apply.py` 開頭的說明）。新的 token 依錄製順序插在前一個已存在的 token 後面，所以要附上 `order`。官方譯名用 `lookup.py` 查：

```bash
uv run tools/lookup.py "Teleporter" "Shrine of the Mountain"
```

用字的慣例見 repo 根目錄 README 的「修改或新增翻譯」。

### 4. 檢查、套用、模擬安裝

```bash
uv run tools/check.py patch.json            # 有問題的條目要是 0
uv run tools/apply.py patch.json --dry      # 只檢查格式
uv run tools/apply.py patch.json            # 寫進 mods 檔
uv run tools/simulate.py --profile Purist_v5   # 要看到 ok = True，沒有標籤不一致的訊息
```

最後跑全部測試（`uv run --with pytest --with "OpenCC>=1.1.9" pytest`），更新 README「目前有這 N 個模組」的表格（版本、條數；條數只算有 `zh-TW` 的條目）。
