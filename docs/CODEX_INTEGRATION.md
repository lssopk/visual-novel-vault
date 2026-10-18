# Codex 云端写入接口接入

## 接入边界

这是一套**通用 HTTP REST API**，不是已自动连接到 OpenAI Codex 的内置插件。只有你在 Codex 的运行环境配置好 HTTPS URL 和 API Token 后，Codex 才能调用。任何支持 HTTPS 的自动化程序都可以使用同一接口。

1. VPS 部署并通过 `https://your-domain.example` 反代本机 `127.0.0.1:6099`。
2. 创建独立 API Key：`docker compose exec app python manage.py create-key --name codex`。
3. 在 Codex 的 Secrets/环境变量中配置 `VAULT_BASE_URL` 和 `VAULT_API_TOKEN`，**不要提交到 GitHub**。
4. 让 Codex 读取 `/api/v1/openapi.json`，或使用下面的 curl/Python 例子。

## 权限

密钥支持 `games:read`, `games:write`, `chapters:read`, `chapters:write`, `entries:read`, `entries:write`, `characters:read`, `characters:write`, `links:read`, `links:write`, `theories:read`, `theories:write`, `progress:write`。

例如只允许记录剧情和笔记，**禁止自动解锁**：

```bash
docker compose exec app python manage.py create-key --name codex-notes --scopes games:read,chapters:read,entries:read,entries:write,characters:read,theories:read,theories:write
```

建议默认使用上面的最小权限密钥。若要 Codex 自动创建游戏和章节，再另外添加 `games:write,chapters:write`。只有确实需要时才赋予 `progress:write`，否则 Codex 无法解锁章节。

## API 请求

所有写入请求使用 `Content-Type: application/json` 和 `Authorization: Bearer ...`。

```bash
curl -fsS "$VAULT_BASE_URL/api/v1/games" -H "Authorization: Bearer $VAULT_API_TOKEN"

curl -fsS -X POST "$VAULT_BASE_URL/api/v1/games" \
 -H "Authorization: Bearer $VAULT_API_TOKEN" -H 'Content-Type: application/json' \
 -d '{"title":"海猫鸣泣之时","genre":"推理","description":"个人游戏记录"}'
# 返回 id，例如 ga_xxx

curl -fsS -X POST "$VAULT_BASE_URL/api/v1/chapters" \
 -H "Authorization: Bearer $VAULT_API_TOKEN" -H 'Content-Type: application/json' \
 -d '{"game_id":"ga_xxx","number":1,"title":"EP1","overview":"本章总结","caution":"注意区分证言和事实"}'
# 返回 id，例如 ch_xxx

curl -fsS -X POST "$VAULT_BASE_URL/api/v1/entries" \
 -H "Authorization: Bearer $VAULT_API_TOKEN" -H 'Content-Type: application/json' \
 -d '{"chapter_id":"ch_xxx","kind":"event","title":"重要事件","body":"这里是事件内容","happened_at":"10月4日","source":"游戏文本","confidence":"reported","position":1}'
```

其他资源：`/characters`、`/links`、`/theories`。列表 GET 使用 `game_id` 或 `chapter_id` 参数；`PATCH /{resource}/{id}` 更新；`DELETE /{resource}/{id}` 删除。

### 防剧透与资料质量

- 写入资料时，先确认**游戏 ID、章节 ID、是否已经读完**，不要把后续章节事实混入当前章节。
- 为每条证据写 `confidence`：`confirmed`（已核实）、`reported`（角色陈述）、`inferred`（推论）、`unverified`（待核实）。
- 对人物使用 `first_chapter`，对关系也使用 `first_chapter`，浏览器会按当前解锁进度过滤。
- 不要让 Codex 自行推断章节已通关。解锁必须由用户明确确认。
- API Key 可以读取未解锁资料，**不要把它放进浏览器前端**。

## 可直接交给 Codex 的任务模板

> 你是我的视觉小说调查档案助手。使用环境变量 VAULT_BASE_URL 和 VAULT_API_TOKEN 调用 /api/v1 的 REST API。先 GET /games 与 /chapters 查找对应 ID，避免重复创建。严格按我明确说已通关的章节写入资料，不要使用未来章节知识；人物、事件、证据、假说分开存储。证据标明来源与可信度。写入前列出拟更新章节，得到我的确认后再 POST/PATCH。不要调用 unlock 接口，不要在输出或日志中显示 API Token。

## OpenAPI

`GET /api/v1/openapi.json` 可供 Codex 读取接口结构。此版是基本 OpenAPI 3.1 文档，参数、对象示例见 JSON 文件。
