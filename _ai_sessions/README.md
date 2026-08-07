# AI Sessions Archive

备份本机与 `E:\project` 相关的 Claude Code / Grok 对话与记忆。

## 目录说明

- `claude-code/projects/` — Claude Code 按工作目录隔离的会话（`*.jsonl` 对话记录 + `memory/` 记忆）
- `claude-code/history.jsonl` — Claude Code 全局命令/会话历史
- `claude-code/plans/` — Claude Code 计划文件
- `claude-code/file-history/` — 会话关联的文件编辑快照
- `claude-code/settings.json` — Claude Code 设置（无真实 API key）
- `grok/sessions/` — Grok 在 E:\project 各子目录下的会话
- `grok/memtrace/` — Grok 记忆追踪日志
- `grok/config.toml` — Grok 配置（不含 auth）
- `project-local/` — 项目内 `.claude` / `.grok` / `.cursor` 配置副本

## 未收录（安全/体积）

- `~/.grok/auth.json`（含 refresh_token，绝不上传）
- `~/.grok/bin`、`downloads`、`vendor` 等二进制/安装包
- `~/.claude/telemetry`、`cache`、`image-cache`
- 会话内 `tool-results` 大输出目录

## 路径名对照

Claude 的 `E--project-temu` 等目录名是把 `E:\project\temu` 中的 `:\` 和 `\` 替换成 `-` 后的编码。
Grok 的会话目录已解码为 `E__project__子目录` 形式。
