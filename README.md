# wecom2notes

企业微信消息同步到笔记软件的开源服务。

`wecom2notes` 从企业微信会话内容存档拉取消息，统一落到 SQLite，再按路由规则投递到 Craft、Obsidian/Markdown、Logseq、Notion、WebDAV 或 Git 管理的笔记库。

## 支持矩阵

| 类型 | 状态 | 说明 |
| --- | --- | --- |
| 企业微信会话内容存档 | 已支持 | 通过官方 SDK 拉取和解密归档消息 |
| Craft | 已支持 | 支持兼容旧绑定和 target adapter |
| Obsidian / Markdown | 已支持 | 写入本地 Markdown 目录或 vault |
| Logseq | 已支持 | 复用 Markdown 写入并输出 block 风格 |
| Notion | 已支持 | 支持 page append 或 database page |
| WebDAV | 已支持 | 通过 GET/PUT 追加远程 Markdown 文件 |
| Git 笔记库 | 已支持 | 写入 Markdown 后可选自动提交 |
| 个人微信自动抓取 | 不属于首期稳定能力 | 可通过导入器处理导出的聊天文件 |

## 架构

```text
Source Connector
  WeCom Archive / Importer

Message Normalizer
  UnifiedMessage / AttachmentInfo

Storage + Queue
  SQLite / source_cursors / deliveries

Router
  user binding / DB routes / config/routes.json / env targets

Target Adapter
  Craft / Obsidian / Markdown / Logseq / Notion / WebDAV / Git
```

## 快速开始

```bash
cp .env.example .env
./docker-deploy.sh
curl http://localhost:8001/
curl http://localhost:8001/openapi.json
```

查看日志：

```bash
docker logs -f wecom2notes
```

Mac 本地测试完成后关闭容器：

```bash
docker compose down
```

## 配置

企业微信最小配置：

```env
WECOM_TOKEN=your_wecom_token
WECOM_CORP_ID=your_corp_id
WECOM_ENCODING_AES_KEY=your_encoding_aes_key
WECOM_APP_SECRET=your_archive_secret
WECOM_PRIVATE_KEY_PATH=private_key.pem
```

Obsidian/Markdown 最小配置：

```env
OBSIDIAN_VAULT_PATH=/notes
OBSIDIAN_BASE_DIR=WeCom
OBSIDIAN_MODE=daily
```

Docker 默认将 `HOST_NOTES_DIR` 挂载到容器 `/notes`。

## 管理接口

- `GET /`：健康检查。
- `GET /openapi.json`：OpenAPI。
- `GET /metrics`：Prometheus 文本 metrics。
- `GET /admin/target-types`：查看支持的 target 类型。
- `GET /admin/destinations`：查看投递目标。
- `POST /admin/destinations`：创建或更新投递目标。
- `GET /admin/routes`：查看路由规则。
- `POST /admin/routes`：创建路由规则。
- `GET /admin/deliveries`：查看投递状态。
- `POST /admin/replay`：按 `source + msg_id` 手动重放。

## 兼容 Craft 绑定

旧版 Craft 绑定 API 仍可用：

```bash
curl -X POST http://localhost:8001/bindings \
  -H "Content-Type: application/json" \
  -d '{
    "wecom_openid": "用户OpenID",
    "craft_link_id": "Craft链接ID",
    "craft_document_id": "Craft文档ID",
    "craft_token": "pdk_xxx",
    "display_name": "显示名称"
  }'
```

## 批量导入

支持 CSV、Markdown、HTML 和文本文件导入：

```bash
python scripts/import_messages.py path/to/export.csv --source import
```

导入后的消息会进入同一套路由和投递链路。

## 文档

- [企业微信配置](docs/wecom.md)
- [Craft 目标](docs/craft.md)
- [Obsidian / Markdown 目标](docs/obsidian.md)
- [部署](docs/deployment.md)
- [排障](docs/troubleshooting.md)
- [发布检查清单](docs/release-checklist.md)

## 安全边界

- 不要把 `.env`、私钥、数据库和真实笔记库内容提交到仓库。
- Docker 镜像不再复制 `.env` 和 `private_key.pem`，敏感配置应通过环境变量、volume 或 secret 注入。
- 日志中避免输出完整 token、secret 和原始消息内容。

## 许可证

MIT
