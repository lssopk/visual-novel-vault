# AI 操作手册｜视觉小说个人调查档案馆（v1）

> 给 Codex、Claude Code、ChatGPT Work 或其他能够发起 HTTPS 请求的 AI 使用。**只需提供 HTTPS 网站根地址、独立 API Token 和本文件地址**。不需要服务器 SSH、GitHub 写入权限或数据库访问权限。
>
> 本手册依据本仓库的 `server.py`、`manage.py`、`db.py` 接口实现编写；机器可读接口见 `GET /api/v1/openapi.json`。API Key 必须保密，不得写入 GitHub、前端、笔记、日志或回复。

## 0. 交给 AI 的最简任务指令

将下面这句话和**网站 HTTPS 根地址**、**API Token（通过 AI 平台的 Secrets 安全配置）**一起交给 AI：

> 请读取 https://github.com/lssopk/visual-novel-vault/blob/main/docs/AI_OPERATIONS.md 并遵守全部操作规范。目标网站地址由 VAULT_BASE_URL 提供，API 密钥由 VAULT_API_TOKEN 提供。你是我的视觉小说个人调查档案助手：先检查连通性、查找现有游戏和章节，再按我实际游玩进度整理事件、证据、人物关系与推理。避免重复创建；绝不自行解锁章节、引入未来剧透或删除我的历史推理。操作结束反馈新建/修改了哪些记录；不要输出密钥。

**前置条件**：AI 所在环境必须支持向该域名发送 HTTPS 请求。仅仅阅读本文，并不会让普通聊天自动获得 HTTP 调用能力；如果环境没有相关工具，AI 应明确说明并给出待执行请求，不得假装已写入。

## 1. 连接约定

| 配置项 | 示例（仅示意，不是真实凭据） | 用途 |
| --- | --- | --- |
| `VAULT_BASE_URL` | `https://novel.example.com` | HTTPS 网站根地址，末尾不带 `/api/v1` |
| `VAULT_API_TOKEN` | `<从服务器生成的专用密钥>` | 通过密钥管理功能保存，不要贴进公开文档 |

请求构造：`BASE = VAULT_BASE_URL.rstrip('/')`，`API = BASE + '/api/v1'`。

- **认证**：`Authorization: Bearer <VAULT_API_TOKEN>`（实际密钥以 `vnv_` 开头）。
- **写入格式**：`Content-Type: application/json`，UTF-8 JSON 对象。
- **健康检查**：`GET /api/v1/health`，**无需密钥**，正常返回 `{"status":"ok","version":"1.0"}`。
- **验证密钥**：`GET /api/v1/auth/me`，应返回 `authenticated: true` 和 `api_key: true`。
- **接口发现**：`GET /api/v1/openapi.json`，无需密钥；`/api-docs` 为网页说明。
- **请求体大小**：不超过 262144 字节。不要一次发送超大文章。
- **当前版本**：无批量创建、事务批处理、分页游标、附件上传或幂等键；所有关联对象必须取得真实 ID 后逐条提交。
- **跨域**：浏览器前端不支持任意外站跨域调用。应从 Codex/代理的**服务端**请求 API，勿在网页 JS 内暴露密钥。

### 最小连通性测试（使用已配置的环境变量）

```bash
curl -fsS "${VAULT_BASE_URL%/}/api/v1/health"
curl -fsS "${VAULT_BASE_URL%/}/api/v1/auth/me" \
  -H "Authorization: Bearer $VAULT_API_TOKEN"
```

如没有办法将 Token 安全注入环境变量，先请用户配置 Secrets；**不得要求把 Token 提交到仓库或保存进脚本**。

## 2. 可以做什么：资源和字段

所有路径以下省略 `/api/v1` 前缀。列表响应为 `{"items":[...]}`，读取单条和 POST/PATCH 返回单个 JSON 对象；POST 成功是 **201**，PATCH 成功是 **200**，DELETE 返回 `{"ok":true}`。

| 资源 | GET 列表（必需筛选参数） | POST 创建的必需字段 | 可选创建字段 / PATCH 可修改字段 |
| --- | --- | --- | --- |
| games 游戏 | `GET /games` | `title` | `original_title, description, genre`，PATCH 也可修改 `title` |
| chapters 章节 | `GET /chapters?game_id=GAME_ID` | `game_id, number, title` | `overview, caution`，PATCH 可改 `number, title, overview, caution` |
| entries 章节档案 | `GET /entries?chapter_id=CHAPTER_ID` | `chapter_id, kind, title` | `body, happened_at, source, confidence, position`，PATCH 可改这些以及 `kind, title` |
| characters 人物 | `GET /characters?game_id=GAME_ID` | `game_id, name` | `bio, first_chapter`，PATCH 可改 `name` 等 |
| links 人物关系 | `GET /links?game_id=GAME_ID` | `game_id, source_id, target_id` | `label, first_chapter`，PATCH 可改 `source_id, target_id, label, first_chapter` |
| theories 个人假说 | `GET /theories?chapter_id=CHAPTER_ID` | `chapter_id, title` | `claim, support, counter, status`，PATCH 可改 `title` 等 |

完整 CRUD：

- `GET /{resource}/{id}` 读取单条。
- `POST /{resource}` 创建。
- `PATCH /{resource}/{id}` **仅发送要修改的字段**。
- `DELETE /{resource}/{id}` 删除；**未经用户明确要求及确认，AI 不得调用**。
- `POST /chapters/{id}/unlock` 解锁是单独操作，需要 `progress:write`，请求 JSON 为 `{"confirmation":"EP1"}`（编号按对应章节替换）。**默认禁止 AI 调用；即使具备权限，除非用户逐章明确确认通关，不得解锁。**

字段约束：

- `number, first_chapter, position` 必须是整数，0–9999；`number` 和 `first_chapter` 必须至少 1。
- 章节编号在同一游戏内唯一；重复创建可能返回 409。
- `kind` 五选一：`summary`（章概要）、`event`（事件时间线）、`evidence`（证据/证言）、`note`（个人笔记）、`tip`（无剧透提醒）。
- `confidence` 四选一：`confirmed`（当前进度下明确证实）、`reported`（人物说法/转述）、`inferred`（推理结论）、`unverified`（待核对）。**角色说了不等于事实成立。**
- `status` 四选一：`open`（待验证）、`supported`（现有证据支持）、`disputed`（存在反证）、`closed`（阶段性结案）。不代表故事最终真相。
- `first_chapter` 控制人物及关系在普通浏览器的可见范围。新角色/新关系应填写**首次出现且不会剧透的章节**，不能习惯性全部填 1。
- `happened_at` 是描述文本（例如 `10月4日 夜间`），不是强制 ISO 时间戳；请按作品内信息记录，未知则留空。
- 游戏、章节、事件等由服务器生成 ID，如 `ga_...`、`ch_...`、`en_...`。**必须使用 API 实际返回的 ID，不要编造。**
- 必需关联 ID：创建章节要有效 `game_id`；创建 entries/theories 要有效 `chapter_id`；人物关系的两名人物须属于相同游戏。
- 标题一般限 180 字，正文 `body/overview` 限 30000 字，`claim/support/counter` 各限 20000 字。长内容拆成独立条目。

## 3. AI 的标准操作流程（必须遵守）

### A. 先确立游玩边界

1. 从用户这次提供的文字确认**作品名称**、**目前章节**、**玩到了哪段**，以及**是否已经通关该章**。不能用旧资料猜测用户已通关，也不能把游戏全部剧情当作已知。
2. 用户只说“刚玩到某个场景”时，可记录为当前章节**进行中笔记**，**不能解锁**章节。
3. 如缺作品/章节或会造成误写，先问一个必要的问题；不要自行搜索未来剧情来补全。
4. **默认只依据用户提供的游玩记录和已经明确完成的剧情整理**；未经用户要求，不搜索攻略、Wiki、解析文章或完整剧透。
5. API Token 是可信读取者，可能读到**未解锁章节**、未来人物和隐藏线索！读 `/chapters`、`/characters`、`/links` 时只用必要的 ID 与进度字段；**不要把未来章内容送到回答、总结或当前章节**。如不确定进度，宁可询问。

### B. 查重后再写（避免多次运行生成重复记录）

1. `GET /games`，按标准名/别名匹配。没有时才创建游戏。
2. `GET /chapters?game_id=...`，按章节编号匹配。没有时才创建章节。
3. `GET /entries?chapter_id=...`、`GET /theories?chapter_id=...`，按 **kind + title + 原内容/来源** 识别已有条目。
4. 同一个事实更新已有记录用 `PATCH`；不同时间点的推理应**新增一条带时间/版本含义的 note 或 theory**，不要覆盖用户最初的思路。本系统目前没有自动的“推理版本历史”，不要声称存在。
5. 写人物前查 `GET /characters?game_id=...`；写关系前查 `GET /links?game_id=...`。关系使用真实人物 ID，避免重复连线。
6. 仅发送需更新的字段，先验证响应码与返回 ID。失败不可当作成功。
7. 结束向用户报告：游戏、章节、新增/更新的条数及对应标题；绝不显示 Token。

### C. 内容归档规则

- 游戏总体信息 → `games`；一章概览 → `chapters.overview`；可独立检索的事件、证据、心得 → `entries`。
- 事件 `kind=event`：尽可能填写 `happened_at`、`position`，保留事件顺序。
- 证据 `kind=evidence`：`source` 写来源（人物证言、屏幕文字、用户猜测等），`confidence` 写证据层级。不能把个人猜测伪装成作品明示的事实。
- 推理 `theories`：`claim` 写假说；`support` 记现有支持；`counter` 记现有反证；`status` 随阶段更新。
- 人物关系 `links`：只写当前已知的关系，不提前补真身份、秘密关系或最终真相。
- 无剧透提示 `kind=tip`：引导注意细节，但**不能暗示未来反转或结局**。
- 若只获得零碎资料，宁可保留“不确定/待确认”，不要自行编造精确时间、台词、死亡顺序或动机。

### D. 高风险行为的硬性约束

- 默认不执行任何 DELETE、整库覆盖、清空、自动解锁或批量修改。如果用户确实请求，先明确列出影响范围并获得确认；删除可能级联移除关联记录。
- 不擅自创建带未来情节的内容；即使 API 允许向未解锁章节写入，也只能写用户已经提供的这一章资料。
- 不向外部服务、搜索引擎、公共日志或 issue 发送管理员密码/API Token；终端不要使用会打印 Authorization 头的调试模式。
- 如果 `VAULT_BASE_URL` 只有 `http://` 而不支持 HTTPS，**不要传输 API Token 或管理员密码**；先要求用户配置 TLS。
- 尊重用户对私人推理的表述，避免“强行纠正”尚未揭晓的谜题。
- 尽量使用受限权限密钥；避免给日常整理任务 `progress:write`。

## 4. 端到端请求实例（先读后写）

下面使用 shell + curl；AI 也可以用 Python、Node.js 或平台内置 HTTP 工具发送等价请求。不要把示例 ID 原样提交。

### 步骤 1：查找游戏

```bash
curl -fsS "${VAULT_BASE_URL%/}/api/v1/games" \
  -H "Authorization: Bearer $VAULT_API_TOKEN"
```

如果 `items` 中没有目标游戏，创建：

```bash
curl -fsS -X POST "${VAULT_BASE_URL%/}/api/v1/games" \
  -H "Authorization: Bearer $VAULT_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"示例游戏","genre":"悬疑推理","description":"我的个人调查档案"}'
```

记录响应中的真实 `id`，下称 `GAME_ID`。

### 步骤 2：查找/创建对应章节

```bash
curl -fsS "${VAULT_BASE_URL%/}/api/v1/chapters?game_id=$GAME_ID" \
  -H "Authorization: Bearer $VAULT_API_TOKEN"
```

列表中没有 `number=1` 才创建：

```bash
curl -fsS -X POST "${VAULT_BASE_URL%/}/api/v1/chapters" \
  -H "Authorization: Bearer $VAULT_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary "{\"game_id\":\"$GAME_ID\",\"number\":1,\"title\":\"第1章\",\"overview\":\"依据当前已玩内容整理\"}"
```

记录真实 `chapter.id`，下称 `CHAPTER_ID`。新建章节默认**未解锁**，不要额外调用 unlock。

### 步骤 3：查重、记录事件

```bash
curl -fsS "${VAULT_BASE_URL%/}/api/v1/entries?chapter_id=$CHAPTER_ID" \
  -H "Authorization: Bearer $VAULT_API_TOKEN"
```

没有重复记录才创建：

```bash
curl -fsS -X POST "${VAULT_BASE_URL%/}/api/v1/entries" \
  -H "Authorization: Bearer $VAULT_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary "{\"chapter_id\":\"$CHAPTER_ID\",\"kind\":\"event\",\"title\":\"初次调查\",\"body\":\"这里填写用户实际看到的事件\",\"happened_at\":\"第一天\",\"source\":\"用户游玩记录\",\"confidence\":\"reported\",\"position\":1}"
```

若已存在同一条目，以真实 `ENTRY_ID` 执行：

```bash
curl -fsS -X PATCH "${VAULT_BASE_URL%/}/api/v1/entries/$ENTRY_ID" \
  -H "Authorization: Bearer $VAULT_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"body":"在原有基础上核实并修订的内容"}'
```

### 步骤 4：记录个人假说

```bash
curl -fsS -X POST "${VAULT_BASE_URL%/}/api/v1/theories" \
  -H "Authorization: Bearer $VAULT_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary "{\"chapter_id\":\"$CHAPTER_ID\",\"title\":\"调查假说 A\",\"claim\":\"用户目前的猜测\",\"support\":\"目前支持它的已知线索\",\"counter\":\"仍有疑点\",\"status\":\"open\"}"
```

人物：`POST /characters` + `{"game_id":"实际ID","name":"人物名","bio":"目前已知描述","first_chapter":1}`。

关系：先取得两个人物 ID，再 `POST /links` + `{"game_id":"实际ID","source_id":"实际人物ID","target_id":"实际人物ID","label":"已确认的关系","first_chapter":1}`。

## 5. 错误处理与排障

| HTTP 状态码 | 含义 | AI 应采取的行动 |
| --- | --- | --- |
| 200 / 201 | 读取/修改成功、创建成功 | 使用返回值验证结果、保存真实 ID |
| 400 | 参数、JSON、字段类型、章节关联等不合法 | 检查字段及 ID，必要时先 GET |
| 401 | 密钥缺失/无效/已撤销 | 停止写入，请用户检查安全配置 |
| 403 | 权限不足（例如缺少 `chapters:write`） | 不绕过权限；说明缺少的 scope |
| 404 | 资源不存在或路径不对 | 校正 ID、完整路径和版本前缀 |
| 405 | 请求方法或路径组合不被支持 | 按本手册改为支持的方法 |
| 409 | 同一个游戏内章节编号重复 | GET 查到已有章节，再 PATCH（如用户要求） |
| 423 | 浏览器会话读取了封存章节 | 不尝试绕过用户进度限制 |
| 429 | 管理员密码登录过于频繁 | 暂停重试；AI 应使用 Bearer Token |
| 500 | 服务器内部异常 | 停止反复写入；检查是否已有部分写入 |
| 502 / 503 | 代理/后端不可达或尚未初始化 | 停止写入，请用户检查 VPS 和部署日志 |

**不要将网络超时等同于写入失败**：因为请求可能已在服务器提交。重试 POST 之前，重新 GET 列表查重；否则会产生重复记录。

## 6. 密钥的创建与权限管理（由用户在 VPS 上执行）

推荐用于**自动整理游戏、创建章节、更新笔记，但禁止 AI 解锁**的密钥：

```bash
docker compose exec app python manage.py create-key --name ai-archive \
  --scopes games:read,games:write,chapters:read,chapters:write,entries:read,entries:write,characters:read,characters:write,links:read,links:write,theories:read,theories:write
```

更保守的只读密钥：

```bash
docker compose exec app python manage.py create-key --name ai-reader \
  --scopes games:read,chapters:read,entries:read,characters:read,links:read,theories:read
```

查看/撤销：

```bash
docker compose exec app python manage.py list-keys
docker compose exec app python manage.py revoke-key KEY_ID
```

**创建密钥的命令仅用于服务器管理员，不属于 AI 日常远程操作。** Token 只在创建时完整显示一次；撤销后不能继续使用。不要在外部公开仓库中提交自己的真实域名和 Token 配置文件。

## 7. 给 AI 的完成报告格式

> 已连接档案馆：是/否  
> 游戏及章节：……  
> 本次记录：新增 N 条事件、N 条证据、N 条个人假说；更新 N 条已有条目  
> 涉及记录：标题与 ID（不包含任何 Token）  
> 章节解锁：未执行  
> 需要你确认的问题：……（如有）

**如果没有实际发出成功的 API 请求，只能写“准备完成/未写入”，禁止报告“已同步”。**
