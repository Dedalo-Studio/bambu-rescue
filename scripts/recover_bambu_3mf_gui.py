# -*- coding: utf-8 -*-
import contextlib, io, os, threading, traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
import recover_bambu_3mf as engine

BG, CARD, FIELD, TEXT, MUTED, GREEN, GREEN2, RED = "#0B1117", "#121C24", "#192630", "#EAF4F1", "#8FA6A1", "#00AE68", "#19D181", "#FF6B6B"
GUIDE_TEXT = """1. 程序已经帮你找好了最近一次崩溃记录。先看第一栏的日期和时间，是不是你出问题的那一次。
2. 如果时间不对，点右边的“浏览”，打开对应日期，再选择里面以时间开头的那个文件夹。
3. 第二栏是修好的文件放在哪里，保持默认即可，修好后会出现在你的“文档”文件夹。
4. 第三栏通常不用你管。程序会尝试找到崩溃前保存过的同一个工程，用它补回丢失的模型。
5. 最后点击“备份并开始恢复”。程序会先备份原数据，再修复，不会覆盖你的原文件。
如果本工具恢复失败，可以尝试使用 AI Skill：recover-bambu-3mf 进行深度排查。
如果 EXE 和 AI Skill 都无法解决，再把下方日志截图，联系收费技术支持。"""


def latest_crash_folder():
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Temp" / "bamboo_model"
    found = []
    if base.exists():
        for p in base.rglob("*"):
            if p.is_dir() and (p / ".3mf").is_file() and (p / "3D").is_dir():
                found.append(p)
    return max(found, key=lambda p: (p / ".3mf").stat().st_mtime) if found else None


def find_original_project(crash):
    origin = crash / "origin.txt"
    if not origin.exists(): return None
    raw = origin.read_bytes()
    values = []
    for enc in ("utf-8-sig", "gb18030", "mbcs"):
        try:
            text = raw.decode(enc).strip().strip('"')
            if text: values.append(text)
        except (UnicodeError, LookupError): pass
    for value in values:
        p = Path(value)
        if p.is_file() and p.suffix.lower() == ".3mf": return p
    names = {Path(v).name for v in values if Path(v).name.lower().endswith(".3mf")}
    for base in (Path.home()/"Desktop", Path.home()/"Documents", Path.home()/"Downloads"):
        if base.exists():
            for name in names:
                matches = list(base.rglob(name))
                if matches: return max(matches, key=lambda p: p.stat().st_mtime)
    return None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bambu Rescue · 3MF Crash Recovery")
        self.geometry("900x720"); self.minsize(760, 620); self.configure(bg=BG)
        self.input_var, self.output_var, self.fallback_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.status_var = tk.StringVar(value="READY  ·  等待检查")
        self._styles(); self._build(); self._autofill()

    def _styles(self):
        s = ttk.Style(self); s.theme_use("clam")
        s.configure("TFrame", background=BG); s.configure("Card.TFrame", background=CARD)
        s.configure("TLabel", background=BG, foreground=TEXT)
        s.configure("Muted.TLabel", background=BG, foreground=MUTED)
        s.configure("Card.TLabel", background=CARD, foreground=TEXT)
        s.configure("Hint.TLabel", background=CARD, foreground=MUTED)
        s.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT, bordercolor="#31434D", padding=9)
        s.configure("TButton", background="#263640", foreground=TEXT, padding=(14, 9), borderwidth=0)
        s.map("TButton", background=[("active", "#344B57")])
        s.configure("Accent.TButton", background=GREEN, foreground="#04150E", padding=(22, 11), font=("Microsoft YaHei UI", 10, "bold"))
        s.map("Accent.TButton", background=[("active", GREEN2), ("disabled", "#315547")])

    def _build(self):
        top = tk.Frame(self, bg=BG); top.pack(fill="x", padx=28, pady=(24, 12))
        tk.Label(top, text="BAMBU  /  RESCUE", bg=BG, fg=GREEN2, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(top, text="3MF 崩溃恢复工具", bg=BG, fg=TEXT, font=("Microsoft YaHei UI", 25, "bold")).pack(anchor="w", pady=(4, 2))
        tk.Label(top, text="从 Bambu Studio 临时缓存重建项目 · 自动备份 · 全包校验", bg=BG, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        tk.Label(top, text="作者 / MakerWorld：小岛秀夫   ·   收费临时技术支持：耀阳（作者本人）   ·   单次30元起   ·   微信：d570565010", bg=BG, fg="#F5C96A", font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w", pady=(7, 0))

        guide = ttk.Frame(self, style="Card.TFrame", padding=18); guide.pack(fill="x", padx=28, pady=10)
        ttk.Label(guide, text="第一次使用？照着下面做就行", style="Card.TLabel", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w")
        ttk.Label(guide, text=GUIDE_TEXT, style="Hint.TLabel", justify="left", wraplength=810).pack(anchor="w", pady=(8, 0))

        form = ttk.Frame(self, style="Card.TFrame", padding=18); form.pack(fill="x", padx=28, pady=10)
        self._row(form, "① 软件崩溃时留下的文件夹", "通常已经自动选好，你只要核对时间", self.input_var, self.choose_input, 0)
        self._row(form, "② 修好的文件放到哪里", "保持默认即可，完成后去“文档”里找", self.output_var, self.choose_output, 1)
        self._row(form, "③ 崩溃前保存过的同一个工程", "通常会自动找到；没有找到也可以先试着恢复", self.fallback_var, self.choose_fallback, 2)
        bar = ttk.Frame(form, style="Card.TFrame"); bar.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.inspect_btn = ttk.Button(bar, text="检查候选文件", command=self.inspect); self.inspect_btn.pack(side="left")
        ttk.Button(bar, text="打开缓存位置", command=self.open_default).pack(side="left", padx=8)
        self.recover_btn = ttk.Button(bar, text="备份并开始恢复", style="Accent.TButton", command=self.start_recovery); self.recover_btn.pack(side="right")
        form.columnconfigure(1, weight=1)

        logbox = tk.Frame(self, bg=CARD); logbox.pack(fill="both", expand=True, padx=28, pady=10)
        tk.Label(logbox, text="RECOVERY LOG", bg=CARD, fg=MUTED, font=("Consolas", 9, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        self.log = scrolledtext.ScrolledText(logbox, bg="#081015", fg="#B9D8CF", insertbackground=TEXT, relief="flat", font=("Consolas", 9), height=10, padx=12, pady=10)
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        footer = tk.Frame(self, bg=BG); footer.pack(fill="x", padx=28, pady=(0, 18))
        tk.Label(footer, textvariable=self.status_var, bg=BG, fg=GREEN2, font=("Consolas", 9, "bold")).pack(side="left")
        tk.Label(footer, text="SOURCE SAFE  ·  ZIP64  ·  CRC VERIFIED", bg=BG, fg=MUTED, font=("Consolas", 9)).pack(side="right")

    def _row(self, parent, label, hint, var, command, row):
        box = ttk.Frame(parent, style="Card.TFrame"); box.grid(row=row, column=0, sticky="nw", pady=8)
        ttk.Label(box, text=label, style="Card.TLabel", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w")
        ttk.Label(box, text=hint, style="Hint.TLabel").pack(anchor="w")
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=14, pady=8)
        ttk.Button(parent, text="浏览…", command=command).grid(row=row, column=2, pady=8)

    def _autofill(self):
        p = latest_crash_folder()
        if p:
            self.input_var.set(str(p)); self._suggest_output(p); self._suggest_fallback(p)
            self.status_var.set("FOUND  ·  已自动定位最新崩溃候选")
            self.log.insert("end", f"已自动发现：\n{p}\n\n请核对时间是否与崩溃发生时间一致。\n")
        else:
            self.log.insert("end", "未自动发现候选，请点击“浏览…”手动选择时间戳文件夹。\n")

    def _suggest_output(self, p):
        self.output_var.set(str(Path.home() / "Documents" / f"Bambu_recovered_{p.name.replace('#','_')}.3mf"))
    def _suggest_fallback(self, p):
        original = find_original_project(p)
        self.fallback_var.set(str(original) if original else "")
        if original: self.log.insert("end", f"已自动定位原始母版：\n{original}\n")

    def choose_input(self):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Temp" / "bamboo_model"
        v = filedialog.askdirectory(title="请选择最里面的时间戳项目文件夹", initialdir=str(base if base.exists() else Path.home()))
        if v: self.input_var.set(v); self._suggest_output(Path(v)); self._suggest_fallback(Path(v))
    def choose_output(self):
        v = filedialog.asksaveasfilename(title="保存恢复后的 3MF", defaultextension=".3mf", filetypes=[("3MF 项目", "*.3mf")])
        if v: self.output_var.set(v)
    def choose_fallback(self):
        v = filedialog.askopenfilename(title="选择同一个项目崩溃前最后保存的 3MF", filetypes=[("3MF 项目", "*.3mf"), ("所有文件", "*.*")])
        if v: self.fallback_var.set(v)
    def open_default(self):
        p = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Temp" / "bamboo_model"
        if p.exists(): os.startfile(p)
        else: messagebox.showinfo("未找到缓存", f"默认位置不存在：\n{p}")

    def inspect(self):
        try:
            root = Path(self.input_var.get()).resolve()
            if not root.is_dir(): raise ValueError("路径无效。请选择包含 .3mf 和 3D 的时间戳文件夹。")
            cap = io.StringIO()
            with contextlib.redirect_stdout(cap): engine.inventory(root)
            self.log.delete("1.0", "end"); self.log.insert("end", cap.getvalue()); self.status_var.set("CHECKED  ·  检查完成")
        except Exception as e: messagebox.showerror("检查失败 / Inspection failed", f"无法检查所选文件夹。请确认它包含 .3mf 和 3D 文件夹。\n\nEnglish details:\n{e}")

    def start_recovery(self):
        root, output = Path(self.input_var.get()), Path(self.output_var.get())
        fallback = Path(self.fallback_var.get()) if self.fallback_var.get().strip() else None
        if not root.is_dir() or not output.name:
            messagebox.showwarning("信息不完整 / Missing information", "请选择有效的崩溃项目文件夹和输出位置。\nPlease select a valid crash project folder and output file."); return
        self.recover_btn.configure(state="disabled"); self.inspect_btn.configure(state="disabled")
        self.log.delete("1.0", "end"); self.status_var.set("WORKING  ·  正在备份并恢复，请勿关闭窗口")
        threading.Thread(target=self._recover, args=(root, output, fallback), daemon=True).start()
    def _recover(self, root, output, fallback):
        cap = io.StringIO()
        try:
            with contextlib.redirect_stdout(cap): engine.recover(root.resolve(), output.resolve(), fallback.resolve() if fallback else None)
            self.after(0, self._finish, True, cap.getvalue(), str(output.resolve()))
        except Exception: self.after(0, self._finish, False, cap.getvalue()+traceback.format_exc(), "")
    def _finish(self, ok, text, output):
        self.log.insert("end", text); self.log.see("end"); self.recover_btn.configure(state="normal"); self.inspect_btn.configure(state="normal")
        if ok:
            self.status_var.set("SUCCESS  ·  恢复和校验完成"); messagebox.showinfo("恢复成功 / Recovery completed", f"恢复文件已生成并通过完整性校验。\nThe recovered project passed validation.\n\n{output}")
        else:
            self.status_var.set("FAILED  ·  请查看恢复日志"); messagebox.showerror("恢复失败 / Recovery failed", "请查看下方日志。若提示缺少对象，请选择同一个项目在崩溃前最后手动保存的 3MF；它只用于补齐缺失模型。\n\nCheck the log below. If objects are missing, select the last manually saved 3MF of the same project. It is used only to fill missing models.")


if __name__ == "__main__": App().mainloop()
