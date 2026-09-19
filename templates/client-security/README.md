# AI Client Security Templates

此目录维护主流 AI 编码 Agent（`agy`、`claude`、`codebuddy`、`codex`）的安全防御配置模版。

## 目标与原则

在使用 `--yolo` / `--dangerously-skip-permissions` / `bypassPermissions` 全自动模式时，Agent 会跳过交互式权限询问（Ask）。
主流客户端的权限判定链均遵循：

$$\mathbf{Deny > Ask > Allow}$$

配置 `Deny` 规则能够强制在底层拦截对敏感文件与密钥的访问，即使处于 YOLO 模式也**无法被模型或参数绕过**。

---

## 保护对象

* `~/.mcporter/**`：工蜂/Knot 等 MCP 平台个人令牌及凭证
* `~/.claude.json`：全局认证凭据与已挂载 MCP 配置
* `~/.config/gh/**`：GitHub CLI 访问令牌
* `~/.git-credentials`：Git HTTP 明文凭据
* `~/.ssh/**`：SSH 私钥
* `~/.aws/**`、`~/.config/gcloud/**`：云平台访问密钥
* `**/.env*`：项目工作区中的私密环境变量文件

---

## 客户端配置文件路径与模版对照

| 客户端 | 目标配置文件 | 模版文件 |
| :--- | :--- | :--- |
| **Google Antigravity CLI (`agy`)** | `~/.gemini/antigravity-cli/settings.json` | `agy-settings.json` |
| **Claude Code (`claude` / `tclaude`)** | `~/.claude/settings.json` | `claude-settings.json` |
| **CodeBuddy (`codebuddy`)** | `~/.codebuddy/settings.json` | `codebuddy-settings.json` |
| **OpenAI Codex (`codex`)** | `~/.codex/config.toml` | `codex-config.toml` |

---

## 新机器一键初始化

仓库提供了自动化同步脚本 `scripts/sync_security_settings.py`，它会智能**增量合并** `deny` 规则，而**不会覆盖**你原有的模型选择、插件或界面设置：

```bash
# 1. 预检模式（只显示变更，不写磁盘）
python3 scripts/sync_security_settings.py --dry-run

# 2. 正式应用配置
python3 scripts/sync_security_settings.py
```
