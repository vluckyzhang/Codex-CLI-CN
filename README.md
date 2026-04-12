# Codex-CLI-CN

<p align="center">
  <strong>面向 <code>@openai/codex 0.120.0</code> 的中文兼容补丁项目</strong><br />
  为最新版官方 npm 包提供自动备份、一键注入、一键恢复与中文帮助页适配。
</p>

<p align="center">
  <a href="https://github.com/vluckyzhang/Codex-CLI-CN">项目主页</a> ·
  <a href="./docs/index.html">介绍页</a> ·
  <a href="./NOTICE.md">来源说明</a>
</p>

## 项目说明

`Codex-CLI-CN` 是基于原项目 [`396001000/codex-Chinese`](https://github.com/396001000/codex-Chinese) 思路重做的 `0.120.0` 兼容版本。

截至 **2026 年 4 月 12 日**，npm 上 `@openai/codex` 的 `latest` 标签指向 `0.120.0`。这一版本的 CLI 已经改为“Node 启动器 + 平台原生二进制”结构，旧版直接注入脚本的方式无法原样沿用，所以本项目改成了更稳妥的：

1. 自动定位全局安装目录。
2. 先备份原始 `bin/codex.js`。
3. 注入一个兼容 `0.120.0` 的中文启动器。
4. 仅对“帮助页 / 子命令帮助页 / 共用说明文本”做安全翻译。
5. 保持交互式 TUI 默认透明转发，避免破坏原生终端行为。

## 当前覆盖范围

- `codex --help`
- `codex -h`
- `codex help ...`
- `codex exec --help`
- `codex review --help`
- `codex login --help`
- `codex resume --help`
- 顶层与子命令共享的配置说明、审批说明、沙箱说明、远程模式说明等文本
- 自动备份、恢复、状态检查

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

### 4. 查看状态

```bash
npm run status
```

### 5. 恢复官方启动器

```bash
npm run restore
```

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
│  └─ codex-cn.mjs              # 注入 / 恢复 / 状态检查入口
├─ translations/
│  └─ codex-0.120.0.json        # 0.120.0 帮助页与说明文本翻译表
├─ docs/
│  └─ index.html                # 项目介绍页
├─ CHANGELOG.md                 # 版本记录
├─ NOTICE.md                    # 原作者与来源说明
├─ LICENSE                      # 许可证
└─ README.md
```

## 设计原则

- 不碰 `codex.exe` 原生二进制，降低升级风险。
- 不覆盖用户已有环境，先备份再注入。
- 只翻译当前可安全拦截的文本，优先保证稳定性。
- 所有非代码说明文档默认使用中文。
- 明确标注原作者、原项目和官方上游来源。

## 来源与致谢

- 原中文项目作者：`396001000`
- 原项目地址：<https://github.com/396001000/codex-Chinese>
- 官方上游项目：OpenAI `codex`
- 官方上游地址：<https://github.com/openai/codex>
- 官方 npm 包：`@openai/codex@0.120.0`

如果你希望继续扩展交互式 TUI 的深度汉化，可以在这个仓库基础上继续推进“源码级汉化 + WSL/Rust 构建”的路线；本项目已经把 `0.120.0` 的兼容补丁、文档与仓库结构先搭好了。
