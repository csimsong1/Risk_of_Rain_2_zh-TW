# Risk of Rain 2 繁體中文語言包

把 Risk of Rain 2 內建的簡體中文（`zh-CN`）轉成繁體中文（`zh-TW`）的腳本。
產生的是遊戲原生的語言資料夾，不需要 BepInEx 或任何模組，有沒有裝模組都能用。

**下載安裝包**：到 [Releases](https://github.com/csimsong1/Risk_of_Rain_2_zh-TW/releases/latest) 下載 `RoR2_zh-TW_installer.zip`（[直接下載](https://github.com/csimsong1/Risk_of_Rain_2_zh-TW/releases/latest/download/RoR2_zh-TW_installer.zip)），解壓縮後點兩下 `安裝.bat`，遊戲語言包和模組翻譯會一起裝好。之後再點一次 `安裝.bat`，就會先從 GitHub 更新翻譯再安裝，見[自動更新](#自動更新)。

有用 r2modman 玩模組的話，腳本會順便把幾個模組的繁體中文翻譯裝進你的模組設定檔，見[模組翻譯](#模組翻譯)。

| 檔案 | 用途 |
|---|---|
| `ror2_s2t.py` | 轉換腳本 |
| `overrides/icon.png` | 語言選單上的國旗圖示（中華民國國旗） |
| `mods/` | 模組的繁體中文翻譯，一個模組一個檔案 |
| `plugin/` | 替換模組寫死文字的 BepInEx 外掛（原始碼與編譯好的 `RoR2_zh-TW.HardcodedText.dll`），見[寫死在程式裡的文字](#寫死在程式裡的文字) |
| `test_ror2_s2t.py` | 模組翻譯功能的測試 |
| `make_bundle.py` | 打包成[給朋友的安裝包](#給朋友的安裝包含模組翻譯)，連模組翻譯一起 |
| `test_make_bundle.py` | 打包流程的測試 |
| `ror2_update.py` | 安裝包的「安裝.bat」執行的程式：先從 GitHub [更新翻譯](#自動更新)，再執行 `ror2_s2t.py` |
| `test_ror2_update.py` | 更新程式的測試 |
| `RoR2_zh-TW_1.5.0.zip` | 用 `--zip` 打包的語言包（只有遊戲本體），可直接分享給別人；不在 repo 裡，見[遊戲更新之後](#遊戲更新之後) |

## 安裝打包好的語言包

拿到 zip 的人照這三步做，不需要安裝其他東西：

1. 在 Steam 收藏庫對 Risk of Rain 2 按右鍵 →「管理」→「瀏覽本機檔案」（Epic 版則開啟遊戲的安裝資料夾）。
2. 把 zip 解壓縮到打開的那個資料夾。
3. 開遊戲，在主選單右上角的國旗選單拉到最下面，選「繁體中文」。

移除時先把語言切回別的，再刪掉
`Risk of Rain 2_Data\StreamingAssets\Language\zh-TW` 資料夾。

## 給朋友的安裝包（含模組翻譯）

上面那種 zip 只有遊戲本體的語言資料夾，模組翻譯要另外放進 r2modman 的設定檔。要連模組翻譯一起給朋友，用 `make_bundle.py` 打包：

```bash
uv run make_bundle.py "D:\python_embeded_v3.13.15.7z"
```

它把轉換腳本、更新程式、`mods`、`overrides`、外掛 DLL 和一份可攜式 Python 包成 `RoR2_zh-TW_安裝包.zip`（約 13 MB）。朋友不用安裝任何東西：解壓縮後點兩下 `安裝.bat`，它會先從 GitHub 更新翻譯，再像 `uv run ror2_s2t.py` 一樣把遊戲語言包和模組翻譯一起裝好。壓縮檔裡的 `說明.txt` 寫了安裝、更新、移除，以及找不到遊戲時的做法。

- 參數是一份裝好 pip 的 Python embeddable package（`._pth` 要啟用 `import site`），資料夾或壓縮檔都可以；壓縮檔要安裝 7-Zip 才解得開。原本那份不會被更動。Python 3.11、3.12、3.13 都打包過。
- 打包時會用它的 pip 安裝 OpenCC，需要網路。
- `--output 檔案` 可以改輸出的檔名。

### 發布到 GitHub

安裝包放在 GitHub 的 [Releases](https://github.com/csimsong1/Risk_of_Rain_2_zh-TW/releases/latest)。朋友第一次從那裡下載，之後靠[自動更新](#自動更新)拿到新的翻譯，所以只有這些時候才需要發布新的安裝包：

- `ror2_s2t.py` 開頭的相依套件或 Python 版本改了（舊的安裝包會提示朋友下載新版）。
- 改了 `make_bundle.py` 產生的 `安裝.bat` 或 `說明.txt`。

要先安裝 [GitHub CLI](https://cli.github.com/)（`gh`）並用 `gh auth login` 登入。標籤用發布日期；附件名稱要維持 `RoR2_zh-TW_installer.zip`，README 開頭的直接下載連結指向這個名稱，`#` 後面是頁面上顯示的名稱：

```bash
uv run make_bundle.py "D:\python_embeded_v3.13.15.7z" --output RoR2_zh-TW_installer.zip
gh release create v2026.10.27 "RoR2_zh-TW_installer.zip#RoR2_zh-TW_安裝包.zip" --target main --title "繁體中文語言包 2026-10-27" --notes-file 發布說明.md
```

`發布說明.md` 是頁面上的安裝與更新說明，可以照上一版的 Release 修改。

### 自動更新

`安裝.bat` 執行的是 `ror2_update.py`：先下載 GitHub 上 `main` 分支的壓縮檔（https://github.com/csimsong1/Risk_of_Rain_2_zh-TW ），把安裝包裡的 `ror2_s2t.py`、`ror2_update.py`、外掛 DLL、`mods`、`overrides` 換成最新版本，再用新的 `ror2_s2t.py` 安裝。所以改了翻譯之後，合併到 `main` 並推送，朋友下次點 `安裝.bat` 就會拿到；`main` 等於朋友拿到的版本，在遊戲裡確認過再推。

- `mods`、`overrides` 整個資料夾換成 GitHub 上的內容，repo 刪掉的翻譯，朋友那邊也會刪掉。
- 連不上 GitHub、下載的檔案不完整，或寫入檔案失敗時，照樣用現有的檔案安裝。
- 安裝包裡的 Python 拿掉了 pip，裝不了新的套件。`ror2_s2t.py` 開頭的相依套件或 Python 版本改了的話，舊的安裝包不會更新任何檔案，裝完後提示朋友到 [Releases](https://github.com/csimsong1/Risk_of_Rain_2_zh-TW/releases/latest) 下載新的安裝包。這種時候要重新打包，上傳到 GitHub 的 Releases。
- `安裝.bat` 和 `說明.txt` 是打包時產生的，不會被更新；改了它們也要重新打包。
- `安裝.bat --no-update` 不連 GitHub，只用現有的檔案安裝。在有 `.git` 的資料夾（這個 repo）裡執行時也不會更新，以免蓋掉還沒推送的翻譯。

## 自己產生語言包

需要 Steam 或 Epic 版的 Risk of Rain 2 和 [uv](https://docs.astral.sh/uv/)。
OpenCC 會由 uv 自動安裝。在這個資料夾執行：

```bash
uv run ror2_s2t.py
```

腳本會自動找到用 Steam 或 Epic Games 安裝的遊戲，在語言資料夾裡建立 `zh-TW`；有用 r2modman 的話，也會自動把[模組翻譯](#模組翻譯)裝進每個設定檔。接著到遊戲的國旗選單選「繁體中文」即可。

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

遊戲更新新增的文字不會自動出現在 `zh-TW`，重跑一次腳本就好；用安裝包的人再點一次 `安裝.bat`。
用 `--zip` 分享語言包的話，順便重新打包，檔名改成新的遊戲版本號：

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

目前有這三十一個模組：

| 模組 | 版本 | 翻譯內容 | 條數 |
|---|---|---|---|
| Insurgent | 1.0.2 | 角色、技能、關鍵字、成就、造型名稱 | 31 |
| Xenologist | 1.0.4 | 角色、技能、九種樣本的效果、特殊技能變體、偵察無人機 | 64 |
| LunarDragon | 1.2.5 | 角色、技能、關鍵字、成就、背景故事 | 36 |
| LookingGlass | 1.16.3 | buff 圖示提示的名稱與說明（135 個 buff）；物品數值標籤、技能觸發係數與冷卻時間、傳送門追蹤（外掛） | 269＋268 |
| HUNK | 1.5.3 | 角色、武器與改造零件、專長、任務目標、物品、鑰匙卡、病毒、成就、背景故事；彈藥名稱、畫面中央的提示、無線電對話（外掛） | 505＋49 |
| Dante | 1.0.1 | 角色、技能、惡魔兵器、物品、皮膚、成就、背景故事、米斯歷克斯與虛假子嗣的台詞 | 172 |
| Seamstress | 1.7.4 | 角色、技能、關鍵字、成就、背景故事 | 44 |
| SkinFlavorText | 1.0.1 | 遊戲本體角色、Paladin 與 HUNK 皮膚的說明文字 | 55 |
| Heretic | 1.2.11 | 被動、技能說明、物品、成就 | 8 |
| Celestial War Tank | 2.3.12 | 角色、技能、車體與炮塔、塗裝、成就、背景故事、Mega War Tank（含引擎欄位）、Ancient Scepter 強化技能；燃料量表、坦克編輯器的炮塔選單（外掛） | 368＋21 |
| Minato（Zerneas） | 0.21.1 | 角色、技能、九尾查克拉模式、飛雷神提示、成就、背景故事；熟練度提示（外掛） | 36＋1 |
| Naruto Shippuden（Zerneas） | 0.30.1 | 角色、技能、四尾形態、成就、背景故事；熟練度提示（外掛） | 33＋1 |
| Naruto Sage（Zerneas） | 0.32.1 | 角色、技能、隱藏技能、六尾形態、成就、背景故事；熟練度提示（外掛） | 40＋1 |
| Sasuke Shippuden（Zerneas） | 0.31.3 | 角色、技能、隱藏技能、咒印形態、成就、背景故事；熟練度提示（外掛） | 40＋1 |
| Sasuke Mangekyou（Zerneas） | 0.25.2 | 角色、技能、萬花筒形態、完美閃避提示、成就、背景故事；熟練度提示（外掛） | 33＋1 |
| Naruto Six Paths（Zerneas） | 0.21.2 | 角色、技能、奧義、成就、背景故事；熟練度提示（外掛） | 23＋1 |
| Sasuke Rinnegan（Zerneas） | 0.19.2 | 角色、技能、奧義、關鍵字、成就、背景故事；熟練度提示（外掛） | 22＋1 |
| Haku（Zerneas） | 0.18.1 | 角色、技能、魔鏡冰晶、冰鏡互動提示、造型、成就、背景故事；熟練度提示（外掛） | 30＋1 |
| Zabuza（Zerneas） | 0.6.3 | 角色、技能、霧隱之鬼人、水分身、造型、成就、背景故事；熟練度提示（外掛） | 22＋1 |
| Kizuna（Zerneas） | 0.21.1 | 選角畫面 Variants 分頁裡火影各角色變體的說明；羈絆面板與羈絆說明、教學卷軸、標題畫面開關（外掛） | 6＋276 |
| Miner Unearthed | 1.10.1 | 角色、技能、關鍵字、Ancient Scepter 強化技能、造型、成就、背景故事、首領 Direseeker | 76 |
| Pilot | 0.6.5 | 角色、技能、Ancient Scepter 強化技能、背景故事 | 30 |
| Rocket | 1.1.6 | 角色、技能、Ancient Scepter 強化技能、造型、成就、背景故事 | 34 |
| Paladin | 2.3.2 | 角色、技能、關鍵字、Ancient Scepter 強化技能、造型、成就、背景故事、米斯歷克斯與虛假子嗣的台詞 | 93 |
| Shock Trooper | 1.2.5 | 角色、技能、無人機、造型、成就、背景故事 | 31 |
| Cadet | 1.1.11 | 角色、技能、關鍵字、造型、成就、背景故事 | 27 |
| Scout | 0.9.11 | 角色、技能、關鍵字、Ancient Scepter 強化技能、配裝欄位名稱、造型、成就、背景故事 | 31 |
| Spy | 1.3.4 | 角色、技能、關鍵字、Ancient Scepter 強化技能、配裝欄位名稱、造型、成就、背景故事 | 36 |
| Ivory Bastion | 1.2.2 | 角色名稱與介紹、技能名稱、無人機名稱、buff；技能與關鍵字說明、工程面板、HUD、升級樹、畫面提示（外掛） | 22＋212 |
| PlayerRespawnSystem | 2.2.0 | 兩條禁止重生的聊天訊息；死亡後的重生倒數（外掛） | 2＋10 |
| Survariants | 1.0.9 | 選角畫面 Variants 分頁的標籤；變體清單的 Default 項目（外掛） | 1＋2 |

條數裡「＋」後面的是由外掛替換的寫死文字，見[寫死在程式裡的文字](#寫死在程式裡的文字)。

Heretic、Dante、Miner Unearthed、Pilot、Rocket 與 Paladin 自帶簡體翻譯（Dante、Miner Unearthed 與 Paladin 只有一部分），那些條目是把簡體轉成繁體後對照英文修訂的，其餘由英文翻譯。

Seamstress、Paladin、Cadet、Scout、Spy、Xenologist 的技能數字（傷害、冷卻秒數）和 HUNK 的五條說明會跟著模組設定變動，英文是模組執行時算出來的；譯文是固定的，收錄的是預設設定的版本，改過那些設定的話要自己修改對應的譯文。各檔案開頭的 `notes` 有說明。

Celestial War Tank 的車體、炮塔數值和技能說明裡的重量，是模組從自帶的資源包算出來的；技能說明最後的「技能數值」只在模組設定 Show Extra Skill Info 開啟（預設）時出現，關掉的話英文會少這一段，譯文仍會顯示。

安裝時會寫入這些地方：

- `設定檔\BepInEx\plugins\RoR2_zh-TW\*.language`：LookingGlass 以外的模組。R2API 會自動讀取，並蓋過模組寫死的英文。
- 遊戲的 `Language\zh-TW\mod_*.json`：LookingGlass。它直接查語言資料夾的內容，不經過 R2API。
- `設定檔\BepInEx\plugins\RoR2_zh-TW\*.literals` 和 `RoR2_zh-TW.HardcodedText.dll`：寫死在程式裡的文字（火影系列、Ivory Bastion、LookingGlass、HUNK 等），見下一節。只有裝了這類模組的設定檔才會有。

要移除就刪掉這些檔案。模組更新後版本對不上時，腳本會提醒，新增或改過的文字會顯示英文，其餘照常。

### 寫死在程式裡的文字

有些模組的介面文字直接寫在程式裡，不經過語言表，語言檔翻不到。這部分由專案自己的 BepInEx 外掛 `RoR2_zh-TW.HardcodedText.dll` 處理：

- 翻的範圍：
  - Zerneas 火影系列（程式裡只有英文和西班牙文）：Kizuna（羈絆）模組的選角畫面羈絆面板與 36 組羈絆說明、第一次遊玩時展開的教學卷軸、標題畫面的語音與終結之谷開關，以及各角色形態、奧義、魔鏡冰晶與霧隱之鬼人的熟練度提示。
  - Ivory Bastion：工程（Engineering）升級面板、升級樹與升級卡片、HUD 的狀態列與護盾量表、畫面中央的提示訊息、重設設定的確認對話框。它的技能說明、關鍵字說明和兩個技能名稱是用 R2API 的通用疊加層寫入的，優先於任何語言的翻譯，也交給外掛處理。
  - LookingGlass：物品提示的數值標籤（`Proc Coefficient:` 這類）、技能與裝備圖示提示的冷卻時間和觸發係數、屬性面板的傳送門追蹤、指令選單的無效化提示。
  - HUNK：彈藥名稱、畫面中央的提示訊息（背包已滿、需要鑰匙卡等）、無線電對話、突變提示、降落傘提示。
  - PlayerRespawnSystem 死亡後畫面上的重生倒數、Survariants 變體清單的 Default 項目、Celestial War Tank 的燃料量表與坦克編輯器的炮塔選單。
- 譯文寫在各模組檔案的 `literals`，安裝時轉成外掛讀的 `*.literals` 翻譯表，和外掛一起放進 `RoR2_zh-TW` 資料夾。
- 遊戲啟動時，外掛把模組裡對應的英文字串換成譯文。只有語言選「繁體中文」時才顯示譯文，切到其他語言會恢復原文；它不改模組的檔案，也不影響連線的其他玩家。
- 模組把算好的文字存在別處的（Ivory Bastion 的疊加層），外掛切換語言後會呼叫模組檔案 `refresh` 列出的方法，讓模組依目前的語言重算一次。
- 模組在啟動時就把文字存進資料的（HUNK 的彈藥名稱），等外掛啟動時已經來不及改寫方法；模組檔案的 `walk` 列出存放資料的類別，外掛直接從那個類別的靜態欄位往下找到字串替換。
- 模組更新改了某句英文，那一句就會變回英文，其他照常。BepInEx 的記錄檔（`LogOutput.log`）會寫出改寫了多少地方、有幾條原文找不到。

外掛的原始碼在 `plugin/HardcodedText.cs`。改過之後用 .NET SDK 重新編譯，成品會複製到 `plugin\RoR2_zh-TW.HardcodedText.dll`，安裝腳本和打包都用這個檔案：

```bash
dotnet build plugin -c Release
```

### 翻不到的部分

寫死在程式裡的文字大多可以交給外掛（見上一節），這些是例外：

- PlayerRespawnSystem 含玩家名稱或秒數的重生聊天訊息：由主機組好再送給所有玩家，替換的話，你當主機時其他玩家也會看到中文。
- Celestial War Tank 坦克編輯器的其他文字：在模組資源包的介面裡，不是程式裡的字串。充能條的名稱同時被模組當成識別用的鍵，也沒有翻。
- 各模組的設定名稱與說明（Risk of Options 選單裡看到的）：模組在啟動時就交給 Risk of Options，外掛來不及替換；設定名稱也是設定檔裡的鍵，改了會讓設定失效。
- Risk of Options 選單本身的按鈕與標題：用的是語言 token，理論上語言檔翻得到，但 Risk of Options 自己攔截了 token 查詢，要在遊戲裡試過才知道。

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
- 寫死在程式裡的文字放在 `literals`，`assembly` 是模組的 DLL 名稱。`literals` 依類別分組，鍵是英文原文、值是譯文，只會在那個類別（含它的巢狀類別）裡替換；同一句英文在別的地方可能是物件名稱，分組可以避免改錯：

```json
{
  "assembly": "KizunaMod",
  "literals": {
    "KizunaLobby": { "PARTNERS": "夥伴", "{0} bonded": "已有{0}組羈絆" }
  }
}
```

- 模組把寫死的文字算好後存到別處（例如 R2API 的疊加層）時，換掉字串還不夠，要讓模組重算一次。這時在 `refresh` 列出重算用的靜態方法（不帶參數），外掛切換語言後會呼叫它們：`"refresh": ["IvoryBastion.BastionBalanceText::Refresh"]`。
- 模組在啟動時（`Awake`）就把文字存進資料時，改寫方法已經來不及。這時在 `walk` 列出存放資料的類別（和 `literals` 裡的分組同名），外掛會從它的靜態欄位往下找到那些字串直接替換：`"walk": ["HunkWeaponCatalog"]`。

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

模組翻譯的安裝與檢查邏輯、安裝包的打包流程和更新程式有測試，改腳本之後可以跑：

```bash
uv run --with pytest --with "OpenCC>=1.1.9" pytest
```

## 已知限制

- **用語**：沒列在 `TERMS` 裡的詞仍是大陸用語（例如「循環」「類型」「綁定」）。
- **校對**：錯字是用規則掃描找的，沒有逐句讀過全部文字，背景故事裡可能還有漏掉的。
- **模組文字**：只有 `mods/` 裡的模組有翻譯，其他模組顯示英文。模組自帶的簡體翻譯不會套用到 `zh-TW`。
- **模組翻譯未實測**：token 名稱和英文是從模組的 DLL 分析出來的（較新加入的模組是在遊戲外執行模組註冊文字的程式取得），譯文的標籤也經過腳本檢查，但還沒有在遊戲裡逐條確認顯示。
- **外掛未在遊戲裡實測**：替換寫死文字的外掛只在遊戲外載入模組測過資料替換與方法改寫；介面類的方法因為呼叫 Unity 內部函式，遊戲外無法改寫，要在遊戲裡才看得到結果。
- **安裝包**：只在製作它的電腦上試過（解壓縮後執行 `安裝.bat`，結果和直接跑腳本相同），沒有在別台電腦上試過。從網路下載的 `.bat` 第一次執行時，Windows 可能會跳出安全性警告。
- **自動更新**：在這台電腦上用解壓縮出來的安裝包實際連 GitHub 測過已是最新、有檔案變動、連不上三種情況；相依套件改變時的提示只有自動測試涵蓋。
- **Epic 版**：尋找遊戲的方式和 r2modman 相同（讀 Epic Games Launcher 的安裝記錄 `LauncherInstalled.dat`），只用模擬的記錄檔測過，沒有在裝了 Epic 版的電腦上實測。找不到時用 `--game-dir` 指定。
- **測試範圍**：在遊戲 1.5.0（Steam 版）測試，未裝模組與使用 r2modman 模組設定檔兩種情況都正常顯示。多人連線沒有測過。
- **文字來源**：遊戲本體的文字是官方簡體中文翻譯轉換而來。repo 和安裝包裡都沒有這些文字，是在使用者的電腦上轉換的；用 `--zip` 打包的語言包則含有轉換後的文字，公開散布前請自行斟酌。
