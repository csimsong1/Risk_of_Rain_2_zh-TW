# Risk of Rain 2 繁體中文語言包

把 Risk of Rain 2 內建的簡體中文（`zh-CN`）轉成繁體中文（`zh-TW`）的腳本。
產生的是遊戲原生的語言資料夾，不需要 BepInEx 或任何模組，有沒有裝模組都能用。

有用 r2modman 玩模組的話，腳本會順便把幾個模組的繁體中文翻譯裝進你的模組設定檔，見[模組翻譯](#模組翻譯)。

| 檔案 | 用途 |
|---|---|
| `ror2_s2t.py` | 轉換腳本 |
| `overrides/icon.png` | 語言選單上的國旗圖示（中華民國國旗） |
| `mods/` | 模組的繁體中文翻譯，一個模組一個檔案 |
| `test_ror2_s2t.py` | 模組翻譯功能的測試 |
| `make_bundle.py` | 打包成[給朋友的安裝包](#給朋友的安裝包含模組翻譯)，連模組翻譯一起 |
| `test_make_bundle.py` | 打包流程的測試 |
| `RoR2_zh-TW_1.5.0.zip` | 打包好的語言包，可直接分享給別人（只有遊戲本體） |

## 安裝打包好的語言包

拿到 zip 的人照這三步做，不需要安裝其他東西：

1. 在 Steam 收藏庫對 Risk of Rain 2 按右鍵 →「管理」→「瀏覽本機檔案」。
2. 把 zip 解壓縮到打開的那個資料夾。
3. 開遊戲，在主選單右上角的國旗選單拉到最下面，選「繁體中文」。

移除時先把語言切回別的，再刪掉
`Risk of Rain 2_Data\StreamingAssets\Language\zh-TW` 資料夾。

## 給朋友的安裝包（含模組翻譯）

上面那種 zip 只有遊戲本體的語言資料夾，模組翻譯要另外放進 r2modman 的設定檔。要連模組翻譯一起給朋友，用 `make_bundle.py` 打包：

```bash
uv run make_bundle.py "D:\python_embeded_v3.13.15.7z"
```

它把轉換腳本、`mods`、`overrides` 和一份可攜式 Python 包成 `RoR2_zh-TW_安裝包.zip`（約 13 MB）。朋友不用安裝任何東西：解壓縮後點兩下 `安裝.bat`，就等於在他的電腦上執行一次 `uv run ror2_s2t.py`，遊戲語言包和模組翻譯會一起裝好。壓縮檔裡的 `說明.txt` 寫了安裝、移除，以及找不到遊戲時的做法。

- 參數是一份裝好 pip 的 Python embeddable package（`._pth` 要啟用 `import site`），資料夾或壓縮檔都可以；壓縮檔要安裝 7-Zip 才解得開。原本那份不會被更動。Python 3.11、3.12、3.13 都打包過。
- 打包時會用它的 pip 安裝 OpenCC，需要網路。
- `--output 檔案` 可以改輸出的檔名。

改了翻譯之後重新打包再傳一次；或只把 `mods` 資料夾傳給朋友，蓋掉原本的再點一次 `安裝.bat`。

## 自己產生語言包

需要 Steam 版的 Risk of Rain 2 和 [uv](https://docs.astral.sh/uv/)。
OpenCC 會由 uv 自動安裝。在這個資料夾執行：

```bash
uv run ror2_s2t.py
```

腳本會自動找到 Steam 上的遊戲，在語言資料夾裡建立 `zh-TW`；有用 r2modman 的話，也會自動把[模組翻譯](#模組翻譯)裝進每個設定檔。接著到遊戲的國旗選單選「繁體中文」即可。

也可以用一般的 Python：`pip install OpenCC` 後執行 `python ror2_s2t.py`（開發時只用 uv 測過）。

### 選項

| 選項 | 說明 |
|---|---|
| `--game-dir 路徑` | 遊戲安裝資料夾，自動尋找失敗時使用 |
| `--zip 檔案` | 轉換後另外打包成 zip，方便分享 |
| `--profile 設定檔` | [模組翻譯](#模組翻譯)只裝進這個 r2modman 設定檔（名稱或路徑）；不指定就裝進所有設定檔 |
| `--name 名稱` | 語言選單上顯示的名稱，預設「繁體中文」 |
| `--source` / `--target` | 來源與輸出的語言資料夾，預設 `zh-CN` / `zh-TW` |

## 遊戲更新之後

遊戲更新新增的文字不會自動出現在 `zh-TW`，重跑一次腳本就好。
要給朋友的話順便重新打包，檔名改成新的遊戲版本號：

```bash
uv run ror2_s2t.py --zip RoR2_zh-TW_1.5.1.zip
```

## 模組翻譯

模組的文字大多只有英文，沒有簡體可以轉，所以這部分是人工翻譯，放在 `mods/` 資料夾。

不用加任何選項：腳本會自動找到 r2modman 的所有設定檔（`%APPDATA%\r2modmanPlus-local\RiskOfRain2\profiles`），把翻譯裝進每一個；設定檔沒有安裝的模組會略過，不會多出檔案。r2modman 沒有把「目前選用的設定檔」記在讀得到的地方，所以是全部都裝。

只想裝進其中一個，或設定檔不在預設位置時，用 `--profile` 指定名稱或完整路徑：

```bash
uv run ror2_s2t.py --profile Purist_v4
```

目前有這八個模組：

| 模組 | 版本 | 翻譯內容 | 條數 |
|---|---|---|---|
| Insurgent | 1.0.2 | 角色、技能、關鍵字、成就、造型名稱 | 31 |
| LunarDragon | 1.2.3 | 角色、技能、關鍵字、成就、背景故事 | 36 |
| LookingGlass | 1.16.0 | buff 圖示提示的名稱與說明（83 個 buff） | 165 |
| HUNK | 1.5.3 | 角色、武器與改造零件、專長、任務目標、物品、鑰匙卡、病毒、成就、背景故事 | 505 |
| Dante | 0.0.89 | 角色、技能、惡魔兵器、物品、皮膚、成就、背景故事 | 164 |
| Seamstress | 1.7.3 | 角色、技能、關鍵字、成就、背景故事 | 44 |
| SkinFlavorText | 1.0.1 | 遊戲本體角色、Paladin 與 HUNK 皮膚的說明文字 | 55 |
| Heretic | 1.2.11 | 被動、技能說明、物品、成就 | 8 |

Heretic 與 Dante 自帶簡體翻譯（Dante 只有一部分），那些條目是把簡體轉成繁體後對照英文修訂的，其餘由英文翻譯。

Seamstress 的技能數字（傷害、冷卻秒數）和 HUNK 的五條說明會跟著模組設定變動，英文是模組執行時算出來的；譯文是固定的，收錄的是預設設定的版本，改過那些設定的話要自己修改對應的譯文。各檔案開頭的 `notes` 有說明。

安裝時會寫入兩個地方：

- `設定檔\BepInEx\plugins\RoR2_zh-TW\*.language`：LookingGlass 以外的模組。R2API 會自動讀取，並蓋過模組寫死的英文。
- 遊戲的 `Language\zh-TW\mod_*.json`：LookingGlass。它直接查語言資料夾的內容，不經過 R2API。

要移除就刪掉這些檔案。模組更新後版本對不上時，腳本會提醒，新增或改過的文字會顯示英文，其餘照常。

### 翻不到的部分

這些文字寫死在模組的程式裡，不經過語言表，語言檔沒辦法翻：

- LookingGlass 的物品數值標籤（`Proc Coefficient:` 這類）
- PlayerRespawnSystem 的聊天訊息與復活倒數
- HUNK 的彈藥名稱、畫面中央的提示訊息（背包已滿、需要鑰匙卡等）與無線電對話
- Risk of Options 選單，以及各模組的設定名稱與說明

LookingGlass 的屬性面板是例外，它的文字存在設定裡，可以自己改。關閉遊戲後，用 r2modman 的 Config editor 開啟 `droppod.lookingglass.cfg`（或直接編輯設定檔的 `BepInEx\config\droppod.lookingglass.cfg`），把 `[Stats Display]` 底下這兩個設定值換成下面的內容：

`Stats Display String`

```text
<margin-left=0.6em><size=115%>屬性</size>\n傷害：[damage]\n攻擊速度：[attackSpeed]\n暴擊率：[critWithLuck]\n生命值再生：[regen]\n護甲：[armor] | [armorDamageReduction]\n移動速度：[speed]\n跳躍：[availableJumps] / [maxJumps]\n擊敗：[killCount]\nDPS：[dps]\n連擊：[combo]\n</margin>
```

`Secondary Stats Display String`

```text
<margin-left=0.6em><size=115%>屬性</size>\n傷害：[damage]\n攻擊速度：[attackSpeed]\n暴擊率：[critWithLuck]\n流血機率：[bleedChanceWithLuck]\n生命值再生：[regen]\n護甲：[armor] | [armorDamageReduction]\n移動速度：[speed]\n跳躍：[availableJumps] / [maxJumps]\n總擊敗：[killCountRun]\n最高連擊：[maxComboThisRun]\n山之神龕：[mountainShrines]\n傳送門：[portals] \n</margin>
```

### 修改或新增翻譯

`mods/` 裡每個檔案對應一個模組，`en` 是從模組擷取的英文原文，`zh-TW` 是譯文，改完重跑腳本即可：

```json
{
  "mod": "mwmw-LunarDragon",
  "version": "1.2.3",
  "loader": "r2api",
  "strings": {
    "MIYOWI_LUNAR_DRAGON_NAME": { "en": "Lunar Dragon", "zh-TW": "月球巨龍" }
  }
}
```

- `mod` 是模組在 `plugins` 底下的資料夾名稱，`version` 是翻譯所依據的版本。
- `loader` 填 `r2api`（模組用 R2API 註冊文字，絕大多數是這種）或 `language-folder`（模組自己查語言資料夾，例如 LookingGlass）。
- 沒有 `zh-TW` 的條目會略過，遊戲顯示英文。
- 有些模組沒有另外註冊 token，而是直接把英文句子當 token 用（例如 HUNK 的專長 `Marathon Runner`）。這種文字用英文原文當鍵就翻得到，`en` 和鍵相同；原文只要差一個字就對不上。
- 譯文裡的 `<style=...>` 標籤和 `{0}` 佔位符要和原文一致，順序可以不同；不一致時腳本不會安裝那個模組。

## 自訂

三種調整都是改完重跑腳本。

**換國旗或其他檔案**：把檔案放進 `overrides` 資料夾，檔名和語言資料夾裡的相同（例如 `icon.png`），它會取代來源語言的同名檔案。遊戲原本的圖示是 16×11 的 PNG，放大一點的圖也可以，遊戲會自動縮放。

**換用語**：在 `ror2_s2t.py` 開頭的 `TERMS` 加一行，左邊是轉成繁體字後的大陸用語，右邊是想要的寫法。

```python
"點擊": "點選",
```

**修錯字**：在 `FIXES` 加一行，左邊是轉錯的寫法（可以用正規表示式），右邊是正確寫法。盡量多帶前後幾個字，避免改到別的地方。

```python
"仿生髮電站": "仿生發電站",
```

## 運作方式

1. 用 OpenCC 的 `s2tw` 把簡體字轉成臺灣字形的繁體字，只換字不換詞。
2. 套用 `TERMS` 用語表（鼠標→滑鼠、屏幕→螢幕、服務器→伺服器、幾率→機率等）。
3. 套用 `FIXES` 修正一個簡體字對應多個繁體字時轉錯的地方（並／併、發／髮、幹／乾等）。
4. 檢查每一行在漢字以外的內容（鍵名、顏色標籤、`{0}` 佔位符、標點）完全沒變，有變就不寫入。

沒有用 OpenCC 內建的臺灣用語詞庫（`s2twp`），因為它在遊戲文本會誤轉，例如「的士兵」變成「計程車兵」、「呼出火焰」變成「撥出火焰」、「擴展包」變成「擴充套件包」。

遊戲的 JSON 不是標準格式，所以腳本只做文字替換，不會用 JSON 函式庫重新輸出。

## 測試

模組翻譯的安裝與檢查邏輯、安裝包的打包流程有測試，改腳本之後可以跑：

```bash
uv run --with pytest --with "OpenCC>=1.1.9" pytest
```

## 已知限制

- **用語**：沒列在 `TERMS` 裡的詞仍是大陸用語（例如「循環」「類型」「綁定」）。
- **校對**：錯字是用規則掃描找的，沒有逐句讀過全部文字，背景故事裡可能還有漏掉的。
- **模組文字**：只有 `mods/` 裡的模組有翻譯，其他模組顯示英文。模組自帶的簡體翻譯不會套用到 `zh-TW`。
- **模組翻譯未實測**：token 名稱是從模組的 DLL 靜態分析出來的，譯文的標籤也經過腳本檢查，但還沒有在遊戲裡逐條確認顯示。
- **安裝包**：只在製作它的電腦上試過（解壓縮後執行 `安裝.bat`，結果和直接跑腳本相同），沒有在別台電腦上試過。從網路下載的 `.bat` 第一次執行時，Windows 可能會跳出安全性警告。
- **測試範圍**：在遊戲 1.5.0（Steam 版）測試，未裝模組與使用 r2modman 模組設定檔兩種情況都正常顯示。多人連線沒有測過。
- **文字來源**：內容是官方簡體中文翻譯轉換而來，公開散布前請自行斟酌。
