# AGENTS.md — 视觉小说个人调查档案馆 AI 工作约定

本仓库是 **幕间 · 个人视觉小说调查档案馆**，同时包含网站源码与 Codex/AI 的 HTTP API。

## 对接网站，而不是修改源码

如果用户让你**整理游玩记录、增加游戏、写章节、证据、人物关系、假说**，请通过网站 HTTPS API，而不是通过 GitHub 修改源码或数据库：

1. **首先阅读 [docs/AI_OPERATIONS.md](docs/AI_OPERATIONS.md)**（强制的操作契约：接口字段、权限、查重、防剧透、错误处理）。
2. 从 AI 运行环境的 Secrets/环境变量读取 `VAULT_BASE_URL` 和 `VAULT_API_TOKEN`。**不得把密钥写进文件、GitHub、终端输出、聊天回复或网页 JS。**
3. 调用 `GET /api/v1/health` 检查站点，再用 Bearer Token 调用 `GET /api/v1/auth/me` 验证身份。
4. 查询并复用游戏 ID、章节 ID 和已有记录；按用户**明确提供的当前游玩进度**记录内容，禁止使用未来剧情或通关后的解析。
5. 不自行解锁章节、不自动删除记录、不覆盖旧推理；写入结束后通过 GET 校验并告知用户具体变动。
6. 环境不支持 HTTPS 请求或无法取得 Token 时，直接说明限制，**不要声称已写入**。

**注意**：API Token 可能拥有读取未解锁章节的能力。即便接口返回更多数据，也只处理当前明确允许的剧情进度；不要暴露未解锁章节资料。

## 给用户的快捷说明

只需三个输入：**HTTPS 网站地址**、**API Token（安全配置为 Secret）**、**本仓库 [AI 操作手册](docs/AI_OPERATIONS.md)**。访问 API 不需要 SSH、Docker 或 GitHub 写入权限。

API 基础地址：`$VAULT_BASE_URL/api/v1`

OpenAPI：`$VAULT_BASE_URL/api/v1/openapi.json`

## 修改项目代码时

- 先阅读 `server.py`、`db.py` 和现有测试；不要把文档中的期望当作已实现的功能。
- 保持服务器端防剧透、权限 scopes、会话 CSRF、数据库安全和现有 REST 行为。
- 不要在 Git 中提交密钥、真实用户档案、SQLite 数据库、备份或私人游玩记录。
- API 变更必须同步更新 `docs/AI_OPERATIONS.md`、`docs/CODEX_INTEGRATION.md` 和 `public/openapi.json`。
