# Codex-CLI-CN

<p align="center">
  <img src="./docs/assets/codex-cli-cn-hero.svg" alt="Codex-CLI-CN 横幅" width="920" />
</p>

<p align="center">
  <strong>面向 <code>@openai/codex 0.120.0</code> 的中文兼容补丁项目</strong><br />
  现在同时提供命令行工具与 Windows GUI 图形界面，当前发行版为 <code>v1.120.1</code>。
</p>

<p align="center">
  <a href="https://github.com/vluckyzhang/Codex-CLI-CN">项目主页</a> ·
  <a href="./docs/index.html">介绍页</a> ·
  <a href="./NOTICE.md">来源说明</a>
</p>

## 项目说明

`Codex-CLI-CN` 是基于原项目 [`396001000/codex-Chinese`](https://github.com/396001000/codex-Chinese) 思路重做的 `0.120.0` 兼容版本。

这一版本的 CLI 已经改为“Node 启动器 + 平台原生二进制”结构，旧版直接注入脚本的方式无法原样沿用，所以本项目改成了更稳妥的：

1. 自动搜索全局安装目录，并优先识别系统真正使用的 Codex 路径。
2. 先备份原始 `bin/codex.js`。
3. 注入一个兼容 `0.120.0` 的中文启动器。
4. 将“帮助页 / 登录提示 / 常用状态输出 / 共用说明文本”纳入安全翻译范围。
5. 保持交互式 TUI 主界面默认透明转发，避免破坏原生终端行为。
6. 提供一个可直接使用的 GUI 界面，方便图形化操作。

## 这次更新

- 🚀 新增安装路径检测能力，不再只依赖 `npm root -g`
- 🛡 GUI 默认请求管理员权限启动
- 🧭 修复“使用默认路径”无反应与“检查环境后无结果”问题
- 🧾 修复关于页、日志和子进程回显中的中文乱码
- 🌏 扩大登录提示、常用状态输出与共享说明文本的中文覆盖

## GUI 版

仓库内已经包含 Windows 图形界面源码与打包链路：

```text
gui/codex_cn_gui.py           # GUI 主程序
gui/Codex-CLI-CN-GUI.spec     # PyInstaller 打包配置
scripts/build-gui.ps1         # 一键构建 GUI 发行版
requirements-gui.txt          # GUI 相关依赖
```

GUI 提供以下能力：

- 自动检测 Node.js / npm / Codex CLI 环境
- 自动检测安装路径，并给出候选目录与来源
- 选择目标目录或一键使用推荐路径
- 一键注入中文补丁
- 一键恢复官方启动器
- 实时查看补丁状态与日志输出
- 单独的“关于”页，已统一为 UTF-8 中文内容，修复乱码问题
- 默认请求管理员权限启动，减少写入失败

## 当前覆盖范围

- `codex --help`
- `codex -h`
- `codex help ...`
- `codex exec --help`
- `codex review --help`
- `codex login --help`
- `codex features --help`
- `codex resume --help`
- 顶层与子命令共享的配置说明、审批说明、沙箱说明、远程模式说明等文本
- 登录提示、常用状态输出与部分启动前引导
- 自动探测安装路径、自动备份、恢复、状态检查

> 说明：由于官方 `0.120.0` 核心程序已经是原生二进制，且交互式 TUI 强依赖真实终端能力，为保证兼容性，本版本默认**不拦截交互式主界面输出**。这也是本仓库与旧版 `0.40.0` 汉化方案最大的技术差异。

## 快速开始

### 1. 安装官方 Codex CLI

```bash
npm install -g @openai/codex@0.120.0
```

### 2. 获取本项目

```bash
git clone https://github.com/vluckyzhang/Codex-CLI-CN.git
cd Codex-CLI-CN
```

### 3. 注入中文补丁

```bash
npm run inject
```

### 4. 自动检测安装目录

```bash
npm run locate
```

### 5. 查看状态

```bash
npm run status
```

### 6. 恢复官方启动器

```bash
npm run restore
```

## 启动 GUI

先安装 GUI 依赖：

```bash
pip install -r requirements-gui.txt
```

然后启动图形界面：

```bash
python gui/codex_cn_gui.py
```

如果只想做快速自检：

```bash
python gui/codex_cn_gui.py --self-test
```

## 构建 GUI 发行版

已提供 Windows 一键构建脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-gui.ps1
```

构建完成后会在 `release/` 目录生成 GUI 压缩包。
当前发行包名为 `Codex-CLI-CN-v1.120.1-GUI-win64.zip`。

## 指定目标目录

如果你想先在本地解包目录、测试目录或便携目录中验证补丁，而不是直接改全局 npm 安装目录，可以显式指定目标：

```bash
node scripts/codex-cn.mjs inject --target "D:\\path\\to\\@openai\\codex"
node scripts/codex-cn.mjs status --target "D:\\path\\to\\@openai\\codex"
node scripts/codex-cn.mjs restore --target "D:\\path\\to\\@openai\\codex"
```

## 项目结构

```text
Codex-CLI-CN/
├─ scripts/
│  ├─ codex-cn.mjs              # 注入 / 恢复 / 状态检查入口
│  └─ build-gui.ps1             # GUI 发行版构建脚本
├─ gui/
│  ├─ codex_cn_gui.py           # GUI 主程序
│  └─ Codex-CLI-CN-GUI.spec     # PyInstaller 打包配置
├─ translations/
│  └─ codex-0.120.0.json        # 0.120.0 帮助页与说明文本翻译表
├─ requirements-gui.txt         # GUI 依赖
├─ docs/
│  ├─ assets/                   # SVG 图片素材
│  ├─ index.html                # 项目介绍页
│  └─ release-notes-v1.120.1.md # 当前发行说明
├─ CHANGELOG.md                 # 版本记录
├─ NOTICE.md                    # 原作者与来源说明
├─ LICENSE                      # 许可证
└─ README.md
```

## 设计原则

- 不碰 `codex.exe` 原生二进制，降低升级风险。
- 不覆盖用户已有环境，先备份再注入。
- 只翻译当前可安全拦截的文本，优先保证稳定性与可回退。
- 所有非代码说明文档默认使用中文。
- GUI 与日志输出统一按 UTF-8 处理，避免中文乱码。
- GUI 与补丁脚本统一做多来源安装路径探测，优先照顾 Windows 用户的真实安装习惯。
- 明确标注原作者、原项目和官方上游来源。

## 来源与致谢

- 原中文项目作者：`396001000`
- 原项目地址：<https://github.com/396001000/codex-Chinese>
- 官方上游项目：OpenAI `codex`
- 官方上游地址：<https://github.com/openai/codex>
- 官方 npm 包：`@openai/codex@0.120.0`

如果你希望继续扩展交互式 TUI 的深度汉化，可以在这个仓库基础上继续推进“源码级汉化 + WSL/Rust 构建”的路线；本项目已经把 `0.120.0` 的兼容补丁、文档与仓库结构先搭好了。
