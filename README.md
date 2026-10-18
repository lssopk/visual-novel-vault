# 幕间 · 个人视觉小说调查档案馆

一套可自托管的**通用视觉小说个人调查档案馆**。游戏 → 章节 → 时间线 / 证据 / 人物关系 / 推理笔记。支持手机与桌面浏览器、管理员登录、章节防剧透、Codex 云端 REST API、Docker 一键部署。

## 快速部署

需要 Linux VPS、Docker Engine、Docker Compose v2。仓库为 Private 时，先配置 VPS 的 GitHub SSH Deploy Key。

```bash
git clone git@github.com:lssopk/visual-novel-vault.git
cd visual-novel-vault
chmod +x deploy.sh
./deploy.sh
```

- 服务仅绑定 `127.0.0.1:6099`，你自己配置 HTTPS 反向代理。
- 首次交互运行会提示设置至少 12 位的管理员密码。
- 如果在非交互脚本中部署，请运行 `docker compose exec app python manage.py init-admin`。
- HTTPS 配好后，创建 `.env`，写入 `PUBLIC_HTTPS=1` 并重新运行 `./deploy.sh`，启用 `Secure` 会话 Cookie。
- 访问 `http://127.0.0.1:6099/api/v1/health` 查看服务状态。

> 注意：**不要直接对公网开放 6099 明文 HTTP**。HTTPS 反代应启用访问限制和适当的请求速率限制。仓库为 Private 只是保护源码，不代表站点访问控制已经完成。

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
- 云端 Codex 需可访问你反代后的 HTTPS 域名，并由你在 Codex 环境中配置 API Token。
- 不要将 API Token 写入仓库、浏览器代码、聊天记录或日志。
- 详情见 [Codex 接入说明](docs/CODEX_INTEGRATION.md)。

## 备份

```bash
# 使用 SQLite 在线备份 API，避免直接复制 WAL 活跃数据库
docker compose exec -T app python -c "import sqlite3; c=sqlite3.connect('/data/vault.sqlite3'); b=sqlite3.connect('/tmp/backup.sqlite3'); c.backup(b); b.close(); c.close()"
# 更推荐在宿主机定时备份 Docker volume 并验证恢复；勿把数据库备份提交到 GitHub。
```

## 设计原则

- 个人使用，默认无公开访客模式；所有档案 API 都需要登录或独立 Token。
- 章节初始封存，解锁需明确输入 EP 编号；未解锁正文不会返回给浏览器会话。
- Codex API Key 是可信写入者：按授权范围可写入尚未解锁的章节，但普通浏览器仍不能查看。**API Token 本身具有剧透资料读取权限时应妥善保管。**
- 证据可信度区分「已核实 / 角色陈述 / 推论 / 待核实」，不会替用户判断剧情真相。
- 采用 Python 标准库 + SQLite + 原生 HTML/CSS/JS，不依赖第三方 JS CDN。
- 此版暂不提供多人账户、公开分享、附件上传和跨设备阅读定位同步；可按需求扩展。

## 更新

```bash
git pull --ff-only
./deploy.sh
```

数据保存在独立 Docker Volume 中，代码更新不会清空数据库。