# 幕间 · 个人视觉小说调查档案馆

一套可自托管的**通用视觉小说个人调查档案馆**。游戏 → 章节 → 时间线 / 证据 / 人物关系 / 推理笔记。支持手机与桌面浏览器、管理员登录、章节防剧透、Codex 云端 REST API、Docker 一键部署。

## 快速部署（公网 TCP 6099）

需要 Linux VPS、Docker Engine、Docker Compose v2。GitHub 仓库公开时可直接 HTTPS 克隆，无需 SSH Key。

```bash
git clone https://github.com/lssopk/visual-novel-vault.git
cd visual-novel-vault
chmod +x deploy.sh
./deploy.sh
```

- Docker 默认绑定 **`0.0.0.0:6099`**，允许通过 `http://<VPS公网IPv4>:6099` 直接访问。
- 首次启动在暴露端口之前设置至少 12 位的管理员密码，后续重复运行不会自动重设密码。
- 部署脚本会在 UFW 或 firewalld 已启用时尝试放通 TCP 6099。
- **VPS 服务商的安全组/外部防火墙无法由本脚本保证配置成功**；需要自行允许 TCP 6099。如使用自定义 nftables/iptables，也需检查规则。
- 如果想恢复仅本机访问，在项目根目录新建或编辑 `.env`，加入 `BIND_ADDR=127.0.0.1`，再执行 `./deploy.sh`。
- 检查：`curl http://127.0.0.1:6099/api/v1/health`。

**安全警告**：直接公网 HTTP 适合临时验证连通性，但登录管理员和发送 Codex API Token 都应该使用 **HTTPS**，避免密码和密钥在网络上传输时被窃取。建议配置 Nginx/Caddy HTTPS 反代，并限制管理/API 访问来源。如果反代与此服务在同一台宿主机，建议设置 `BIND_ADDR=127.0.0.1`；Docker 版反代可选择同一 Docker 网络访问，避免持续开放 6099。

HTTPS 配好后，可在 `.env` 加入 `PUBLIC_HTTPS=1` 并重新运行 `./deploy.sh`，启用 Secure 会话 Cookie。**若仍通过明文 HTTP 直接登录，浏览器将不会发送 Secure Cookie。**

## AI 自助操作文档（给 Codex / AI 阅读）

**以后只需要提供三样：HTTPS 网站地址、单独生成的 API Token、[AI 操作手册](docs/AI_OPERATIONS.md)。** AI 会按文档自行检查接口、查找游戏与章节、避免重复，并按已玩进度写入个人游玩记录。

- **完整 AI 指南**：[docs/AI_OPERATIONS.md](docs/AI_OPERATIONS.md)
- **给 Codex 自动读取的仓库说明**：[AGENTS.md](AGENTS.md)
- **网站上可直接访问的 AI 文档入口**：`https://你的域名/ai-guide.txt`（重新部署后生效）
- **OpenAPI**：`https://你的域名/api/v1/openapi.json`

只通过安全的 Secrets 注入 Token，**不得**放进 GitHub 或公开链接。请使用 HTTPS，禁止 AI 自动解锁章节或导入未游玩剧情。

## Codex API

```bash
# 创建独立可撤销的写入密钥（只显示一次）
docker compose exec app python manage.py create-key --name codex
# 查看密钥列表
docker compose exec app python manage.py list-keys
# 撤销密钥
docker compose exec app python manage.py revoke-key key_xxx
```

- API 文档：`/api-docs`，OpenAPI：`/api/v1/openapi.json`
- 云端 Codex 需可访问 HTTPS 域名，并由你在 Codex 环境中配置 API Token。
- 不要将 API Token 写入仓库、浏览器代码、聊天记录或日志。
- 详情见 [Codex 接入说明](docs/CODEX_INTEGRATION.md)。

## 备份

```bash
docker compose exec -T app python -c "import sqlite3; c=sqlite3.connect('/data/vault.sqlite3'); b=sqlite3.connect('/tmp/backup.sqlite3'); c.backup(b); b.close(); c.close()"
```

建议定时备份数据库并定期验证恢复；请勿将数据库备份提交 GitHub。

## 设计原则

- 个人使用，默认无公开访客模式；所有档案 API 都需要登录或独立 Token。
- 章节初始封存，解锁需明确输入 EP 编号；未解锁正文不会返回给浏览器会话。
- Codex API Key 是可信写入者：按授权范围可写入尚未解锁的章节，但普通浏览器仍不能查看。**API Token 如有剧透资料读取权限应妥善保管。**
- 证据可信度区分「已核实 / 角色陈述 / 推论 / 待核实」，不会替用户判断剧情真相。
- 采用 Python 标准库 + SQLite + 原生 HTML/CSS/JS，不依赖第三方 JS CDN。
- 此版暂不提供多人账户、公开分享、附件上传和跨设备阅读定位同步；可按需求扩展。

## 更新

```bash
git pull --ff-only
./deploy.sh
```

数据保存在独立 Docker Volume 中，代码更新不会清空数据库。
