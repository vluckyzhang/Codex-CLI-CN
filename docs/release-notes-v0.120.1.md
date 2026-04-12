# v0.120.1 更新说明

本次版本重点补齐了图形界面与发行版能力，同时修复了中文显示体验问题。

## 新增内容

- 新增基于 Python + CustomTkinter 的 Windows GUI 界面。
- 支持图形化执行环境检测、补丁注入、官方启动器恢复与状态查看。
- 新增 GUI 打包 spec 与一键构建脚本，可直接生成 Windows 发行版。
- 新增 GUI 自检入口，方便快速确认资源是否完整。

## 修复与改进

- 将 GUI “关于”内容、说明文本和日志处理统一为 UTF-8。
- 修复旧版图形界面中中文内容可能出现的乱码问题。
- 为补丁脚本新增 `--json` 输出，便于 GUI 与自动化工具调用。
- 更新 README、介绍页和更新日志，补充 GUI 使用与构建说明。

## 发行包

- `Codex-CLI-CN-v0.120.1-GUI-win64.zip`
  - 包含 `Codex-CLI-CN-GUI.exe`
  - 包含 `README.md`、`NOTICE.md`、`CHANGELOG.md`、`LICENSE`

## 说明

当前补丁仍以 `@openai/codex 0.120.0` 为适配目标。为保证兼容性，交互式原生 TUI 主界面依然保持透明转发，不直接拦截其运行时输出。
