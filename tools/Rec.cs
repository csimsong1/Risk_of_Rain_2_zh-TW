using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Serialization;
using System.Text;
using System.Text.RegularExpressions;
using Mono.Cecil;
using Mono.Cecil.Cil;

namespace Rec {
    public static class R {
        public static List<string[]> Log = new List<string[]>();
        public static void Add(string token, string text) { Log.Add(new string[] { token, text }); }
        public static void Add3(string token, string text, string lang) { Log.Add(new string[] { token, text, lang }); }

        static string Esc(string s) {
            if (s == null) return "null";
            var b = new StringBuilder("\"");
            foreach (char c in s) {
                if (c == '\\') b.Append("\\\\");
                else if (c == '"') b.Append("\\\"");
                else if (c == '\n') b.Append("\\n");
                else if (c == '\r') b.Append("\\r");
                else if (c == '\t') b.Append("\\t");
                else if (c < 0x20) b.Append("\\u" + ((int)c).ToString("x4"));
                else b.Append(c);
            }
            return b.Append('"').ToString();
        }

        public static void Save(string path) {
            using (var w = new StreamWriter(path, false, new UTF8Encoding(false))) {
                w.Write("[\n");
                for (int i = 0; i < Log.Count; i++) {
                    w.Write("  [" + string.Join(", ", Log[i].Select(Esc).ToArray()) + "]");
                    w.Write(i + 1 < Log.Count ? ",\n" : "\n");
                }
                w.Write("]\n");
            }
        }
    }

    public static class Resolver {
        static string[] dirs;
        static Dictionary<string, string> found = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public static void Install(string[] d) {
            dirs = d;
            AppDomain.CurrentDomain.AssemblyResolve += (s, e) => {
                string name = new AssemblyName(e.Name).Name;
                foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
                    if (a.GetName().Name == name) return a;
                string path;
                if (!found.TryGetValue(name, out path)) {
                    path = null;
                    foreach (var dir in dirs) {
                        var hits = Directory.GetFiles(dir, name + ".dll", SearchOption.AllDirectories);
                        if (hits.Length > 0) { path = hits[0]; break; }
                    }
                    found[name] = path;
                }
                return path == null ? null : Assembly.LoadFrom(path);
            };
        }
    }

    public static class Rewriter {
        static readonly Dictionary<Code, OpCode> LongForm = new Dictionary<Code, OpCode> {
            { Code.Br_S, OpCodes.Br }, { Code.Brfalse_S, OpCodes.Brfalse }, { Code.Brtrue_S, OpCodes.Brtrue },
            { Code.Beq_S, OpCodes.Beq }, { Code.Bge_S, OpCodes.Bge }, { Code.Bgt_S, OpCodes.Bgt },
            { Code.Ble_S, OpCodes.Ble }, { Code.Blt_S, OpCodes.Blt }, { Code.Bne_Un_S, OpCodes.Bne_Un },
            { Code.Bge_Un_S, OpCodes.Bge_Un }, { Code.Bgt_Un_S, OpCodes.Bgt_Un }, { Code.Ble_Un_S, OpCodes.Ble_Un },
            { Code.Blt_Un_S, OpCodes.Blt_Un }, { Code.Leave_S, OpCodes.Leave },
        };

        static void Widen(Mono.Cecil.Cil.MethodBody body) {
            foreach (var ins in body.Instructions) {
                OpCode op;
                if (LongForm.TryGetValue(ins.OpCode.Code, out op)) ins.OpCode = op;
                else if (ins.OpCode.Code == Code.Ldloc_S) ins.OpCode = OpCodes.Ldloc;
                else if (ins.OpCode.Code == Code.Stloc_S) ins.OpCode = OpCodes.Stloc;
                else if (ins.OpCode.Code == Code.Ldloca_S) ins.OpCode = OpCodes.Ldloca;
                else if (ins.OpCode.Code == Code.Ldarg_S) ins.OpCode = OpCodes.Ldarg;
                else if (ins.OpCode.Code == Code.Ldarga_S) ins.OpCode = OpCodes.Ldarga;
                else if (ins.OpCode.Code == Code.Starg_S) ins.OpCode = OpCodes.Starg;
            }
        }

        // Pushes a default value of the given type (after the call's arguments were popped).
        static List<Instruction> Default(Mono.Cecil.Cil.MethodBody body, ModuleDefinition mod, TypeReference t) {
            var list = new List<Instruction>();
            string n = t.FullName;
            if (n == "System.Void") return list;
            if (n == "System.Single") { list.Add(Instruction.Create(OpCodes.Ldc_R4, 0f)); return list; }
            if (n == "System.Double") { list.Add(Instruction.Create(OpCodes.Ldc_R8, 0d)); return list; }
            if (n == "System.Int64" || n == "System.UInt64") { list.Add(Instruction.Create(OpCodes.Ldc_I8, 0L)); return list; }
            if (t.IsValueType && !t.IsGenericParameter) {
                string[] ints = { "System.Boolean", "System.Int32", "System.UInt32", "System.Int16", "System.UInt16", "System.Byte", "System.SByte", "System.Char" };
                if (ints.Contains(n)) { list.Add(Instruction.Create(OpCodes.Ldc_I4_0)); return list; }
                var v = new VariableDefinition(mod.ImportReference(t));
                body.Variables.Add(v);
                list.Add(Instruction.Create(OpCodes.Ldloca, v));
                list.Add(Instruction.Create(OpCodes.Initobj, mod.ImportReference(t)));
                list.Add(Instruction.Create(OpCodes.Ldloc, v));
                return list;
            }
            list.Add(Instruction.Create(OpCodes.Ldnull));
            return list;
        }

        public static int Rewrite(string dll, string output, string recordPattern, string stubPattern, string recDll, string[] searchDirs) {
            var resolver = new DefaultAssemblyResolver();
            resolver.AddSearchDirectory(Path.GetDirectoryName(dll));
            foreach (var d in searchDirs) foreach (var sub in Directory.GetDirectories(d, "*", SearchOption.AllDirectories).Concat(new[] { d })) resolver.AddSearchDirectory(sub);
            var asm = AssemblyDefinition.ReadAssembly(dll, new ReaderParameters { AssemblyResolver = resolver });
            var mod = asm.MainModule;
            var recType = AssemblyDefinition.ReadAssembly(recDll).MainModule.GetType("Rec.R");
            var add2 = mod.ImportReference(recType.Methods.First(m => m.Name == "Add"));
            var add3 = mod.ImportReference(recType.Methods.First(m => m.Name == "Add3"));
            var rec = new Regex(recordPattern);
            var stub = new Regex(stubPattern);
            int count = 0;
            foreach (var t in mod.GetTypes()) {
                foreach (var m in t.Methods) {
                    if (!m.HasBody) continue;
                    var body = m.Body;
                    var targets = body.Instructions.Where(i => (i.OpCode.Code == Code.Call || i.OpCode.Code == Code.Callvirt || i.OpCode.Code == Code.Newobj)
                        && i.Operand is MethodReference).ToList();
                    bool widened = false;
                    foreach (var ins in targets) {
                        var mr = (MethodReference)ins.Operand;
                        string full = mr.DeclaringType.FullName + "::" + mr.Name;
                        if (ins.OpCode.Code != Code.Newobj && rec.IsMatch(mr.FullName)) {
                            if (mr.Parameters.Count == 2 && !mr.HasThis) { ins.OpCode = OpCodes.Call; ins.Operand = add2; count++; }
                            else if (mr.Parameters.Count == 3 && !mr.HasThis) { ins.OpCode = OpCodes.Call; ins.Operand = add3; count++; }
                            continue;
                        }
                        if (!stub.IsMatch(full)) continue;
                        if (!widened) { Widen(body); widened = true; }
                        var il = body.GetILProcessor();
                        int pops = mr.Parameters.Count + (mr.HasThis && ins.OpCode.Code != Code.Newobj ? 1 : 0);
                        var seq = new List<Instruction>();
                        for (int k = 0; k < pops; k++) seq.Add(Instruction.Create(OpCodes.Pop));
                        TypeReference ret = ins.OpCode.Code == Code.Newobj ? mr.DeclaringType : mr.ReturnType;
                        var gim = mr as GenericInstanceMethod;
                        if (gim != null && ret.IsGenericParameter) ret = gim.GenericArguments[((GenericParameter)ret).Position];
                        seq.AddRange(Default(body, mod, ret));
                        if (seq.Count == 0) seq.Add(Instruction.Create(OpCodes.Nop));
                        // Keep the original instruction object (branch targets point at it) as the first of the sequence.
                        ins.OpCode = seq[0].OpCode;
                        ins.Operand = seq[0].Operand;
                        var prev = ins;
                        for (int k = 1; k < seq.Count; k++) { il.InsertAfter(prev, seq[k]); prev = seq[k]; }
                    }
                }
            }
            asm.Write(output);
            return count;
        }
    }

    public static class Runner {
        public static string Invoke(Assembly asm, string spec) {
            int sep = spec.LastIndexOf("::");
            string typeName = spec.Substring(0, sep), methodName = spec.Substring(sep + 2);
            var type = asm.GetType(typeName, true);
            var flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly;
            var method = type.GetMethods(flags).Where(x => x.Name == methodName).OrderBy(x => x.GetParameters().Length).First();
            object target = method.IsStatic ? null : FormatterServices.GetUninitializedObject(type);
            // Parameters get default values (null for reference types such as sprites).
            var args = method.GetParameters().Select(p => p.ParameterType.IsValueType ? Activator.CreateInstance(p.ParameterType) : null).ToArray();
            int before = R.Log.Count;
            try {
                method.Invoke(target, args);
                return "ok " + (R.Log.Count - before);
            } catch (Exception e) {
                var x = e is TargetInvocationException && e.InnerException != null ? e.InnerException : e;
                string first = (x.StackTrace ?? "").Split('\n').FirstOrDefault() ?? "";
                return "FAIL after " + (R.Log.Count - before) + ": " + x.GetType().Name + ": " + x.Message + " | " + first.Trim();
            }
        }
    }
}
