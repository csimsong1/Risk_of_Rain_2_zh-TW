using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.CompilerServices;
using System.Text;
using BepInEx;
using HarmonyLib;

namespace RoR2zhTW
{
    // 有些模組把畫面上的文字直接寫在程式裡（英文和西班牙文二選一），不經過遊戲的語言表，語言檔翻不到。
    // 這個外掛在遊戲啟動時依 *.literals 翻譯表換掉那些英文：
    // 方法裡的字串用 Harmony 改寫，靜態建構式建好的資料則直接改欄位的值。
    // 只有遊戲語言是翻譯表指定的語言時才顯示譯文，切到其他語言會恢復原文。
    [BepInPlugin(Guid, "RoR2 zh-TW Hardcoded Text", "1.0.0")]
    public class HardcodedTextPlugin : BaseUnityPlugin
    {
        public const string Guid = "ror2_zh_tw.hardcodedtext";

        private List<Table> tables = new List<Table>();
        private Func<string> currentLanguageName;
        private string lastLanguage;

        private void Awake()
        {
            tables = Table.LoadDirectory(Path.GetDirectoryName(Info.Location), Logger.LogWarning);
            // 用反射取 RoR2.Language，編譯時就不用參考遊戲本體的組件
            var getter = Type.GetType("RoR2.Language, RoR2")
                ?.GetProperty("currentLanguageName", BindingFlags.Public | BindingFlags.Static)?.GetGetMethod();
            if (getter == null)
            {
                Logger.LogError("找不到 RoR2.Language，不替換任何文字");
                tables.Clear();
                return;
            }
            currentLanguageName = (Func<string>)Delegate.CreateDelegate(typeof(Func<string>), getter);
            Logger.LogInfo($"讀到 {tables.Count} 個翻譯表");
        }

        // Start 在所有外掛的 Awake 之後才執行，這時要改寫的模組都已經載入
        private void Start()
        {
            if (tables.Count == 0) return;
            var harmony = new Harmony(Guid);
            var loaded = AppDomain.CurrentDomain.GetAssemblies();
            foreach (var table in tables)
            {
                var assembly = loaded.FirstOrDefault(a => a.GetName().Name == table.Assembly);
                if (assembly == null)
                {
                    Logger.LogInfo($"{table.Source}：沒有載入 {table.Assembly}，略過");
                    continue;
                }
                Patcher.Apply(harmony, assembly, table, Logger.LogInfo, Logger.LogWarning);
            }
            lastLanguage = currentLanguageName();
            Translation.SetActive(tables.Any(t => t.Language == lastLanguage));
        }

        // 遊戲啟動後才設定語言，之後玩家也可能切換；每個畫格比對一次語言名稱，變了就切換譯文和原文
        private void Update()
        {
            if (tables.Count == 0 || currentLanguageName == null) return;
            var name = currentLanguageName();
            if (name == lastLanguage) return;
            lastLanguage = name;
            Translation.SetActive(tables.Any(t => t.Language == name));
        }
    }

    public static class Translation
    {
        private static readonly List<Slot> slots = new List<Slot>();

        public static bool Active { get; private set; }
        public static int SlotCount => slots.Count;

        // 改寫過的方法在原本的英文字串後面呼叫這裡，依目前的語言決定用哪一個
        public static string Pick(string original, string translated) => Active ? translated : original;

        public static void Add(Slot slot, Action<string> warn)
        {
            try
            {
                slot.Apply(Active);
                slots.Add(slot);
            }
            catch (Exception e)
            {
                warn($"無法修改「{Table.Short(slot.Original)}」：{e.Message}");
            }
        }

        public static void SetActive(bool active)
        {
            Active = active;
            foreach (var slot in slots)
            {
                try { slot.Apply(active); }
                catch (Exception) { }
            }
        }
    }

    // 資料裡的一個字串位置，記得原文和譯文，切換語言時寫回其中一個
    public abstract class Slot
    {
        public string Original;
        public string Translated;

        public void Apply(bool active) => Write(active ? Translated : Original);

        protected abstract void Write(string value);
    }

    internal sealed class FieldSlot : Slot
    {
        private readonly object owner;
        private readonly FieldInfo field;

        public FieldSlot(object owner, FieldInfo field) { this.owner = owner; this.field = field; }

        protected override void Write(string value) => field.SetValue(owner, value);
    }

    internal sealed class ArraySlot : Slot
    {
        private readonly Array array;
        private readonly int index;

        public ArraySlot(Array array, int index) { this.array = array; this.index = index; }

        protected override void Write(string value) => array.SetValue(value, index);
    }

    internal sealed class ListSlot : Slot
    {
        private readonly IList list;
        private readonly int index;

        public ListSlot(IList list, int index) { this.list = list; this.index = index; }

        protected override void Write(string value) => list[index] = value;
    }

    internal sealed class DictionarySlot : Slot
    {
        private readonly IDictionary dictionary;
        private readonly object key;

        public DictionarySlot(IDictionary dictionary, object key) { this.dictionary = dictionary; this.key = key; }

        protected override void Write(string value) => dictionary[key] = value;
    }

    // 安裝腳本寫出的翻譯表。格式：
    //   @language zh-TW
    //   @assembly KizunaMod
    //   @type KizunaBook        之後的條目只套用在這個類別（含巢狀類別）
    //   英文<TAB>譯文           \t \n \r \\ 用反斜線跳脫
    public sealed class Table
    {
        public string Source;
        public string Language;
        public string Assembly;
        public readonly Dictionary<string, Dictionary<string, string>> Types =
            new Dictionary<string, Dictionary<string, string>>();

        public static List<Table> LoadDirectory(string directory, Action<string> warn)
        {
            var tables = new List<Table>();
            foreach (var path in Directory.GetFiles(directory, "*.literals").OrderBy(p => p, StringComparer.Ordinal))
            {
                try
                {
                    tables.Add(Parse(File.ReadAllLines(path, new UTF8Encoding(false)), Path.GetFileName(path)));
                }
                catch (Exception e)
                {
                    warn($"{Path.GetFileName(path)} 讀取失敗：{e.Message}");
                }
            }
            return tables;
        }

        public static Table Parse(IEnumerable<string> lines, string source)
        {
            var table = new Table { Source = source };
            Dictionary<string, string> current = null;
            var number = 0;
            foreach (var line in lines)
            {
                number++;
                if (line.Length == 0) continue;
                if (line[0] == '@')
                {
                    var space = line.IndexOf(' ');
                    if (space < 0) throw new FormatException($"第 {number} 行少了值");
                    var value = line.Substring(space + 1);
                    switch (line.Substring(1, space - 1))
                    {
                        case "language": table.Language = value; break;
                        case "assembly": table.Assembly = value; break;
                        case "type":
                            if (!table.Types.TryGetValue(value, out current))
                                table.Types[value] = current = new Dictionary<string, string>();
                            break;
                        default: throw new FormatException($"第 {number} 行的指令不認得");
                    }
                    continue;
                }
                var tab = line.IndexOf('\t');
                if (tab < 0 || current == null) throw new FormatException($"第 {number} 行格式不對");
                current[Unescape(line.Substring(0, tab))] = Unescape(line.Substring(tab + 1));
            }
            if (table.Language == null || table.Assembly == null) throw new FormatException("缺少 @language 或 @assembly");
            return table;
        }

        private static string Unescape(string text)
        {
            if (text.IndexOf('\\') < 0) return text;
            var builder = new StringBuilder(text.Length);
            for (var i = 0; i < text.Length; i++)
            {
                var c = text[i];
                if (c != '\\' || i + 1 == text.Length)
                {
                    builder.Append(c);
                    continue;
                }
                c = text[++i];
                builder.Append(c == 't' ? '\t' : c == 'n' ? '\n' : c == 'r' ? '\r' : c);
            }
            return builder.ToString();
        }

        public static string Short(string text) =>
            text.Length > 40 ? text.Substring(0, 40).Replace("\n", " ") + "…" : text.Replace("\n", " ");
    }

    public static class Patcher
    {
        private const BindingFlags Declared =
            BindingFlags.DeclaredOnly | BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;

        // 每個改寫過的方法要換的字串；Harmony 重新套用修補時（例如別的模組也修補同一個方法）會再查一次
        private static readonly Dictionary<MethodBase, Dictionary<string, string>> rewrites =
            new Dictionary<MethodBase, Dictionary<string, string>>();

        public static void Apply(Harmony harmony, Assembly assembly, Table table, Action<string> info, Action<string> warn)
        {
            var name = assembly.GetName().Name;
            Type[] types;
            try { types = assembly.GetTypes(); }
            catch (ReflectionTypeLoadException e) { types = e.Types.Where(t => t != null).ToArray(); }
            catch (Exception e)
            {
                warn($"{name}：讀不到模組的類別：{Describe(e)}");
                return;
            }

            var transpiler = new HarmonyMethod(typeof(Patcher).GetMethod(nameof(Transpiler), BindingFlags.NonPublic | BindingFlags.Static));
            var seen = new HashSet<string>();
            int methods = 0, slotsBefore = Translation.SlotCount;
            foreach (var group in table.Types)
            {
                var map = group.Value;
                var matched = types.Where(t => InGroup(t, group.Key)).ToList();
                if (matched.Count == 0)
                {
                    warn($"{name}：找不到類別 {group.Key}");
                    continue;
                }
                foreach (var type in matched)
                {
                    try
                    {
                        methods += ApplyToType(harmony, transpiler, type, map, assembly, seen, warn);
                    }
                    catch (Exception e)
                    {
                        warn($"{name}：處理 {type.FullName} 時出錯：{e.Message}");
                    }
                }
            }
            info($"{name}：改寫 {methods} 個方法、{Translation.SlotCount - slotsBefore} 筆資料");
            var missing = table.Types.SelectMany(g => g.Value.Keys).Where(k => !seen.Contains(k)).Distinct().ToList();
            if (missing.Count > 0)
                warn($"{name}：有 {missing.Count} 條原文在模組裡找不到，模組可能改過文字，例如「{Table.Short(missing[0])}」");
        }

        // 回傳改寫的方法數
        private static int ApplyToType(Harmony harmony, HarmonyMethod transpiler, Type type, Dictionary<string, string> map,
            Assembly assembly, HashSet<string> seen, Action<string> warn)
        {
            var name = assembly.GetName().Name;
            var methods = 0;
            // 靜態建構式建好的資料：先確定它跑過，再改資料裡的字串
            var init = type.TypeInitializer;
            if (init != null)
            {
                var hits = Literals(init).Where(map.ContainsKey).ToList();
                if (hits.Count > 0)
                {
                    seen.UnionWith(hits);
                    try
                    {
                        RuntimeHelpers.RunClassConstructor(type.TypeHandle);
                        Walker.Statics(type, map, assembly, warn);
                    }
                    catch (Exception e)
                    {
                        warn($"{name}：無法處理 {type.FullName} 的靜態資料：{e.Message}");
                    }
                }
            }
            foreach (var method in Methods(type))
            {
                var hits = Literals(method).Where(map.ContainsKey).ToList();
                if (hits.Count == 0) continue;
                seen.UnionWith(hits);
                rewrites[method] = map;
                try
                {
                    harmony.Patch(method, transpiler: transpiler);
                    methods++;
                }
                catch (Exception e)
                {
                    warn($"{name}：無法改寫 {type.FullName}::{method.Name}：{Describe(e)}");
                }
            }
            return methods;
        }

        // 例外連同內層例外的訊息，Harmony 的錯誤細節通常在內層
        private static string Describe(Exception e)
        {
            var parts = new List<string>();
            for (; e != null; e = e.InnerException) parts.Add(e.Message);
            return string.Join(" / ", parts);
        }

        // 類別本身或它外層的類別叫這個名字；載入失敗的類別直接略過
        private static bool InGroup(Type type, string group)
        {
            try
            {
                if (type.ContainsGenericParameters) return false;
                while (type.DeclaringType != null) type = type.DeclaringType;
                return type.Name == group;
            }
            catch (Exception)
            {
                return false;
            }
        }

        private static IEnumerable<MethodBase> Methods(Type type)
        {
            foreach (var method in type.GetMethods(Declared))
                if (!method.IsAbstract && !method.ContainsGenericParameters && method.GetMethodBody() != null)
                    yield return method;
            foreach (var constructor in type.GetConstructors(Declared))
                if (!constructor.IsStatic && constructor.GetMethodBody() != null)
                    yield return constructor;
        }

        private static List<string> Literals(MethodBase method)
        {
            try
            {
                return PatchProcessor.ReadMethodBody(method)
                    .Where(i => i.Key == OpCodes.Ldstr && i.Value is string)
                    .Select(i => (string)i.Value)
                    .ToList();
            }
            catch (Exception)
            {
                return new List<string>();
            }
        }

        // 在每個要翻的 ldstr 後面加上 ldstr 譯文、call Translation.Pick
        private static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions, MethodBase original)
        {
            var pick = AccessTools.Method(typeof(Translation), nameof(Translation.Pick));
            rewrites.TryGetValue(original, out var map);
            foreach (var instruction in instructions)
            {
                yield return instruction;
                if (map != null && instruction.opcode == OpCodes.Ldstr && instruction.operand is string text
                    && map.TryGetValue(text, out var translated))
                {
                    yield return new CodeInstruction(OpCodes.Ldstr, translated);
                    yield return new CodeInstruction(OpCodes.Call, pick);
                }
            }
        }
    }

    // 從類別的靜態欄位往下找字串：陣列、清單、字典的值，以及同一個組件裡定義的物件的欄位
    internal static class Walker
    {
        private const int MaxDepth = 12;
        private const BindingFlags InstanceFields =
            BindingFlags.DeclaredOnly | BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        public static void Statics(Type type, Dictionary<string, string> map, Assembly assembly, Action<string> warn)
        {
            var visited = new HashSet<object>(new ReferenceComparer());
            const BindingFlags flags = BindingFlags.DeclaredOnly | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
            foreach (var field in type.GetFields(flags))
            {
                if (field.IsLiteral) continue;
                Visit(field.GetValue(null), () => new FieldSlot(null, field), map, assembly, visited, 0, warn);
            }
        }

        private static void Visit(object value, Func<Slot> slot, Dictionary<string, string> map, Assembly assembly,
            HashSet<object> visited, int depth, Action<string> warn)
        {
            if (value is string text)
            {
                if (map.TryGetValue(text, out var translated))
                {
                    var s = slot();
                    s.Original = text;
                    s.Translated = translated;
                    Translation.Add(s, warn);
                }
                return;
            }
            if (value == null || depth >= MaxDepth || value.GetType().IsValueType || !visited.Add(value)) return;

            switch (value)
            {
                case Array array:
                    if (array.Rank != 1) return;
                    for (var i = 0; i < array.Length; i++)
                    {
                        var index = i;
                        Visit(array.GetValue(i), () => new ArraySlot(array, index), map, assembly, visited, depth + 1, warn);
                    }
                    return;
                case IDictionary dictionary:
                    foreach (var key in dictionary.Keys.Cast<object>().ToList())
                        Visit(dictionary[key], () => new DictionarySlot(dictionary, key), map, assembly, visited, depth + 1, warn);
                    return;
                case IList list:
                    for (var i = 0; i < list.Count; i++)
                    {
                        var index = i;
                        Visit(list[i], () => new ListSlot(list, index), map, assembly, visited, depth + 1, warn);
                    }
                    return;
            }

            for (var type = value.GetType(); type != null && type.Assembly == assembly; type = type.BaseType)
            {
                foreach (var field in type.GetFields(InstanceFields))
                {
                    var owner = value;
                    Visit(field.GetValue(value), () => new FieldSlot(owner, field), map, assembly, visited, depth + 1, warn);
                }
            }
        }

        private sealed class ReferenceComparer : IEqualityComparer<object>
        {
            public new bool Equals(object a, object b) => ReferenceEquals(a, b);

            public int GetHashCode(object value) => RuntimeHelpers.GetHashCode(value);
        }
    }
}
