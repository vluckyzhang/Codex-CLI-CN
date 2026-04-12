#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk


APP_VERSION = "0.120.1"
PROJECT_NAME = "Codex-CLI-CN GUI"
WINDOW_SIZE = "1180x760"
MIN_SIZE = (1080, 700)

ABOUT_TEXT = """\
Codex-CLI-CN GUI

这是 Codex-CLI-CN 的图形界面版本，面向 @openai/codex 0.120.0。

它提供：
1. 自动检测 Node.js、npm 与 Codex CLI 安装状态
2. 一键注入中文补丁
3. 一键恢复官方启动器
4. 实时查看当前补丁状态
5. 直接打开目标目录与项目仓库

来源与致谢：
- 原中文项目作者：396001000
- 原项目地址：https://github.com/396001000/codex-Chinese
- 当前仓库地址：https://github.com/vluckyzhang/Codex-CLI-CN
- 官方上游项目：https://github.com/openai/codex

编码修复说明：
本 GUI 统一以 UTF-8 处理界面文本、说明内容与工具输出，
修复旧版界面中“关于”内容和中文日志可能出现的乱码问题。
"""


@dataclass
class DetectResult:
    node_version: str | None
    npm_version: str | None
    target_root: str | None
    codex_version: str | None
    injected: bool
    backup_path: str | None
    translation_path: str | None
    error: str | None = None


def app_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def decode_output(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "cp936"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


class CodexCnGui:
    def __init__(self) -> None:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title(f"{PROJECT_NAME} v{APP_VERSION}")
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(*MIN_SIZE)

        self.repo_root = app_root()
        self.tool_script = self.repo_root / "scripts" / "codex-cn.mjs"

        self.status_text = ctk.StringVar(value="准备就绪")
        self.target_path = ctk.StringVar(value="")
        self.node_text = ctk.StringVar(value="未检测")
        self.npm_text = ctk.StringVar(value="未检测")
        self.codex_text = ctk.StringVar(value="未检测")
        self.inject_text = ctk.StringVar(value="未检测")
        self.backup_text = ctk.StringVar(value="未检测")

        self.busy = False

        self._build_ui()
        self.root.after(250, self.detect_environment)

    def _build_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(
            self.root,
            width=320,
            corner_radius=0,
            fg_color=("#f4ede1", "#f4ede1"),
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(
            self.root,
            corner_radius=0,
            fg_color=("#fffaf3", "#fffaf3"),
        )
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        self._build_sidebar(sidebar)
        self._build_content(content)

    def _build_sidebar(self, parent: ctk.CTkFrame) -> None:
        hero = ctk.CTkFrame(
            parent,
            fg_color=("#ffefe5", "#ffefe5"),
            border_width=1,
            border_color=("#f1c9b6", "#f1c9b6"),
        )
        hero.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))
        hero.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hero,
            text="Codex-CLI-CN GUI",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#1f2b36",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 6))

        ctk.CTkLabel(
            hero,
            text="给 @openai/codex 0.120.0 准备的一层中文图形外壳",
            font=ctk.CTkFont(size=13),
            justify="left",
            text_color="#5d6673",
            wraplength=250,
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 18))

        path_card = self._card(parent, "目标目录")
        path_card.grid(row=1, column=0, sticky="ew", padx=18, pady=12)
        path_card.grid_columnconfigure(0, weight=1)

        entry = ctk.CTkEntry(
            path_card,
            textvariable=self.target_path,
            height=38,
            corner_radius=12,
            border_color="#d9c8b7",
        )
        entry.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        button_row = ctk.CTkFrame(path_card, fg_color="transparent")
        button_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        button_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            button_row,
            text="浏览目录",
            height=36,
            fg_color="#1f6feb",
            hover_color="#1858b7",
            command=self.choose_target,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            button_row,
            text="使用默认路径",
            height=36,
            fg_color="#f6d8c5",
            hover_color="#efc3a4",
            text_color="#44291e",
            command=self.use_default_target,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        status_card = self._card(parent, "环境状态")
        status_card.grid(row=2, column=0, sticky="ew", padx=18, pady=12)
        status_card.grid_columnconfigure(0, weight=1)

        rows = [
            ("Node.js", self.node_text),
            ("npm", self.npm_text),
            ("Codex 版本", self.codex_text),
            ("补丁状态", self.inject_text),
            ("备份文件", self.backup_text),
        ]
        for index, (label, variable) in enumerate(rows, start=1):
            self._status_row(status_card, index, label, variable)

        action_card = self._card(parent, "操作")
        action_card.grid(row=3, column=0, sticky="ew", padx=18, pady=12)
        action_card.grid_columnconfigure(0, weight=1)

        self.detect_btn = self._action_button(action_card, "检测环境", "#1f6feb", self.detect_environment)
        self.detect_btn.grid(row=1, column=0, sticky="ew", padx=16, pady=(2, 10))

        self.inject_btn = self._action_button(action_card, "注入中文补丁", "#ff6f3c", self.inject_patch)
        self.inject_btn.grid(row=2, column=0, sticky="ew", padx=16, pady=10)

        self.restore_btn = self._action_button(action_card, "恢复官方启动器", "#73442b", self.restore_patch)
        self.restore_btn.grid(row=3, column=0, sticky="ew", padx=16, pady=10)

        self.open_btn = self._action_button(action_card, "打开目标目录", "#e7ebe9", self.open_target_dir, text_color="#1f2b36")
        self.open_btn.grid(row=4, column=0, sticky="ew", padx=16, pady=(10, 16))

        footer = ctk.CTkLabel(
            parent,
            text=f"GUI 版本 {APP_VERSION}\n统一 UTF-8 文本与日志输出",
            justify="left",
            text_color="#6a707b",
            font=ctk.CTkFont(size=12),
        )
        footer.grid(row=4, column=0, sticky="sw", padx=22, pady=(12, 18))

    def _build_content(self, parent: ctk.CTkFrame) -> None:
        topbar = ctk.CTkFrame(
            parent,
            fg_color=("#fff7ee", "#fff7ee"),
            border_width=1,
            border_color=("#eadbc9", "#eadbc9"),
        )
        topbar.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        topbar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            topbar,
            textvariable=self.status_text,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#24313c",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=16)

        self.tabview = ctk.CTkTabview(
            parent,
            fg_color=("#fffaf3", "#fffaf3"),
            segmented_button_fg_color="#f1dfcf",
            segmented_button_selected_color="#ff6f3c",
            segmented_button_selected_hover_color="#ea6230",
            segmented_button_unselected_color="#f1dfcf",
            segmented_button_unselected_hover_color="#ead3c1",
            text_color="#23303b",
        )
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.tabview.add("运行日志")
        self.tabview.add("关于")

        self.log_box = ctk.CTkTextbox(
            self.tabview.tab("运行日志"),
            corner_radius=12,
            fg_color="#fffdf8",
            border_width=1,
            border_color="#e6d8c8",
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self.log_box.pack(fill="both", expand=True, padx=12, pady=12)
        self.log_box.insert("end", "欢迎使用 Codex-CLI-CN GUI。\n")
        self.log_box.insert("end", "先检测环境，再执行注入或恢复操作。\n")
        self.log_box.configure(state="disabled")

        about = self.tabview.tab("关于")
        about.grid_columnconfigure(0, weight=1)
        about.grid_rowconfigure(0, weight=1)

        about_box = ctk.CTkTextbox(
            about,
            corner_radius=12,
            fg_color="#fffdf8",
            border_width=1,
            border_color="#e6d8c8",
            font=ctk.CTkFont(size=14),
            wrap="word",
        )
        about_box.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 8))
        about_box.insert("end", ABOUT_TEXT)
        about_box.configure(state="disabled")

        link_row = ctk.CTkFrame(about, fg_color="transparent")
        link_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        link_row.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            link_row,
            text="打开当前仓库",
            fg_color="#1f6feb",
            hover_color="#1858b7",
            command=lambda: self.open_url("https://github.com/vluckyzhang/Codex-CLI-CN"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            link_row,
            text="打开原项目",
            fg_color="#f6d8c5",
            hover_color="#efc3a4",
            text_color="#44291e",
            command=lambda: self.open_url("https://github.com/396001000/codex-Chinese"),
        ).grid(row=0, column=1, sticky="ew", padx=6)

        ctk.CTkButton(
            link_row,
            text="打开官方上游",
            fg_color="#e7ebe9",
            hover_color="#dae0dd",
            text_color="#1f2b36",
            command=lambda: self.open_url("https://github.com/openai/codex"),
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

    def _card(self, parent: ctk.CTkFrame, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=("#fff9f2", "#fff9f2"),
            border_width=1,
            border_color=("#eadbc9", "#eadbc9"),
        )
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#202b35",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 10))
        return card

    def _status_row(self, parent: ctk.CTkFrame, row: int, label: str, variable: ctk.StringVar) -> None:
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid(row=row, column=0, sticky="ew", padx=16, pady=6)
        container.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            container,
            text=label,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#31404c",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            container,
            textvariable=variable,
            font=ctk.CTkFont(size=13),
            text_color="#5b6572",
            anchor="w",
            justify="left",
            wraplength=170,
        ).grid(row=0, column=1, sticky="w", padx=(10, 0))

    def _action_button(
        self,
        parent: ctk.CTkFrame,
        text: str,
        color: str,
        command,
        text_color: str = "#ffffff",
    ) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            height=42,
            corner_radius=14,
            fg_color=color,
            hover_color=color,
            text_color=text_color,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=command,
        )

    def set_busy(self, busy: bool, message: str | None = None) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.detect_btn.configure(state=state)
        self.inject_btn.configure(state=state)
        self.restore_btn.configure(state=state)
        self.open_btn.configure(state=state)
        if message:
            self.status_text.set(message)

    def append_log(self, text: str) -> None:
        def write() -> None:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"[{timestamp}] {text.rstrip()}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.root.after(0, write)

    def run_process(self, args: list[str], timeout: int = 60) -> tuple[int, str, str]:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["NO_COLOR"] = "1"

        proc = subprocess.run(
            args,
            cwd=self.repo_root,
            capture_output=True,
            text=False,
            timeout=timeout,
            env=env,
        )
        stdout = decode_output(proc.stdout)
        stderr = decode_output(proc.stderr)
        return proc.returncode, stdout, stderr

    def resolve_default_target(self) -> str | None:
        if shutil.which("npm") is None:
            return None
        code, stdout, _ = self.run_process(["npm", "root", "-g"], timeout=30)
        if code != 0:
            return None
        return str(Path(stdout.strip()) / "@openai" / "codex")

    def choose_target(self) -> None:
        selected = filedialog.askdirectory(title="选择 Codex 安装目录")
        if selected:
            self.target_path.set(selected)
            self.detect_environment()

    def use_default_target(self) -> None:
        default_target = self.resolve_default_target()
        if not default_target:
            messagebox.showwarning("提示", "未能自动解析全局 npm 安装目录，请先确认 npm 已安装。")
            return
        self.target_path.set(default_target)
        self.detect_environment()

    def detect_environment(self) -> None:
        if self.busy:
            return
        self.set_busy(True, "正在检测环境...")
        threading.Thread(target=self._detect_environment_thread, daemon=True).start()

    def _detect_environment_thread(self) -> None:
        try:
            result = self._collect_environment()
            self.root.after(0, lambda: self._apply_detect_result(result))
        finally:
            self.root.after(0, lambda: self.set_busy(False, "环境检测完成"))

    def _collect_environment(self) -> DetectResult:
        node_version = None
        npm_version = None

        if shutil.which("node"):
            code, stdout, _ = self.run_process(["node", "--version"])
            if code == 0:
                node_version = stdout.strip()

        if shutil.which("npm"):
            code, stdout, _ = self.run_process(["npm", "--version"])
            if code == 0:
                npm_version = stdout.strip()

        target_root = self.target_path.get().strip() or self.resolve_default_target()
        if target_root and not self.target_path.get().strip():
            self.root.after(0, lambda: self.target_path.set(target_root))

        if not target_root:
            return DetectResult(
                node_version=node_version,
                npm_version=npm_version,
                target_root=None,
                codex_version=None,
                injected=False,
                backup_path=None,
                translation_path=None,
                error="未能解析 Codex 安装目录，请先安装 npm 与 @openai/codex。",
            )

        package_json = Path(target_root) / "package.json"
        if not package_json.exists():
            return DetectResult(
                node_version=node_version,
                npm_version=npm_version,
                target_root=target_root,
                codex_version=None,
                injected=False,
                backup_path=None,
                translation_path=None,
                error="指定目录中未找到 package.json，当前目录不是有效的 Codex 安装目录。",
            )

        package_data = json.loads(package_json.read_text(encoding="utf-8"))
        status_code, stdout, stderr = self.run_process(
            ["node", str(self.tool_script), "status", "--json", "--target", target_root],
            timeout=45,
        )
        if status_code != 0:
            return DetectResult(
                node_version=node_version,
                npm_version=npm_version,
                target_root=target_root,
                codex_version=package_data.get("version"),
                injected=False,
                backup_path=None,
                translation_path=None,
                error=stderr.strip() or stdout.strip() or "状态检查失败。",
            )

        data = json.loads(stdout)
        return DetectResult(
            node_version=node_version,
            npm_version=npm_version,
            target_root=target_root,
            codex_version=data.get("version") or package_data.get("version"),
            injected=bool(data.get("injected")),
            backup_path=data.get("backupPath"),
            translation_path=data.get("translationPath"),
            error=None,
        )

    def _apply_detect_result(self, result: DetectResult) -> None:
        self.node_text.set(result.node_version or "未安装")
        self.npm_text.set(result.npm_version or "未安装")
        self.codex_text.set(result.codex_version or "未检测到")
        self.inject_text.set("已注入" if result.injected else "未注入")
        self.backup_text.set("已存在" if result.backup_path else "未生成")

        if result.error:
            self.append_log(result.error)
            self.status_text.set(result.error)
            return

        self.append_log(f"检测到目标目录：{result.target_root}")
        self.append_log(f"Codex 版本：{result.codex_version}")
        self.append_log(f"补丁状态：{'已注入' if result.injected else '未注入'}")

    def inject_patch(self) -> None:
        self._run_tool_action(
            title="注入中文补丁",
            args=["inject"],
            success_message="中文补丁注入完成。",
        )

    def restore_patch(self) -> None:
        if not messagebox.askyesno("确认恢复", "将恢复官方启动器并移除当前翻译文件，是否继续？"):
            return
        self._run_tool_action(
            title="恢复官方启动器",
            args=["restore"],
            success_message="官方启动器已恢复。",
        )

    def _run_tool_action(self, title: str, args: list[str], success_message: str) -> None:
        if self.busy:
            return

        target_root = self.target_path.get().strip()
        if not target_root:
            messagebox.showwarning("提示", "请先选择或检测 Codex 安装目录。")
            return

        self.set_busy(True, f"{title}中...")

        def worker() -> None:
            try:
                cmd = ["node", str(self.tool_script), *args, "--target", target_root]
                code, stdout, stderr = self.run_process(cmd, timeout=90)
                if stdout.strip():
                    for line in stdout.strip().splitlines():
                        self.append_log(line)
                if stderr.strip():
                    for line in stderr.strip().splitlines():
                        self.append_log(f"错误输出：{line}")
                if code == 0:
                    self.root.after(0, lambda: messagebox.showinfo(title, success_message))
                    self.root.after(0, self.detect_environment)
                else:
                    self.root.after(0, lambda: messagebox.showerror(title, stderr.strip() or stdout.strip() or "执行失败。"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror(title, str(exc)))
            finally:
                self.root.after(0, lambda: self.set_busy(False, f"{title}完成"))

        threading.Thread(target=worker, daemon=True).start()

    def open_target_dir(self) -> None:
        target_root = self.target_path.get().strip()
        if not target_root:
            messagebox.showwarning("提示", "当前没有可打开的目标目录。")
            return
        path = Path(target_root)
        if not path.exists():
            messagebox.showwarning("提示", "目标目录不存在，请先重新检测。")
            return
        os.startfile(path)

    def open_url(self, url: str) -> None:
        import webbrowser

        webbrowser.open(url)

    def run(self) -> None:
        self.root.mainloop()


def run_self_test() -> int:
    root = app_root()
    summary = {
        "app_version": APP_VERSION,
        "repo_root": str(root),
        "tool_script_exists": (root / "scripts" / "codex-cn.mjs").exists(),
        "translations_exists": (root / "translations" / "codex-0.120.0.json").exists(),
        "node_found": shutil.which("node") is not None,
        "npm_found": shutil.which("npm") is not None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(run_self_test())
    if "--version" in sys.argv:
        print(APP_VERSION)
        raise SystemExit(0)
    app = CodexCnGui()
    app.run()
