# WeCom2Craft

企业微信消息转发到 Craft 文档的服务。

它会从企业微信消息存档拉取消息，统一落到 SQLite，再按照用户绑定关系转发到各自的 Craft 文档。当前项目同时提供 FastAPI 接口、后台轮询任务，以及 Docker 部署方式。

`WeCom2Craft` 是当前对外使用的项目名称。仓库内部分运行标识仍保留历史名称 `craftsaver`，例如 Docker 容器名、镜像名和默认数据库文件名；下面示例命令均以当前实际配置为准。

## 适用场景

- 把企业微信消息持续转发到 Craft
- 按用户维度把消息写入不同 Craft 文档
- 统一保存文本、链接、图片、视频、文件等消息
- 通过 API 管理企微用户和 Craft 文档的绑定关系

## 工作流程

1. 企业微信回调命中 `POST /wecom/callback`
2. 服务通过企业微信消息存档 SDK 拉取新消息
3. 消息统一转换后写入 SQLite
4. 按 `wecom_openid -> Craft 文档` 绑定关系转发
5. 图片、视频、文件等媒体资源可上传到腾讯云 COS 后再写入 Craft

如果某个企微用户没有绑定 Craft 文档，对应消息会被记录日志并跳过。

## 技术栈

- Python 3.12
- FastAPI + Uvicorn
- SQLite
- Docker / Docker Compose
- 企业微信消息存档 SDK
- Craft API
- 腾讯云 COS

## 目录结构

```text
.
├── main.py                  # 应用入口，启动 FastAPI 和后台轮询
├── src/
│   ├── api/routers/         # HTTP 路由
│   ├── handlers/            # 消息处理逻辑
│   ├── models/              # Pydantic 模型
│   ├── services/            # WeCom / Craft / COS / DB 服务
│   ├── sql/                 # SQLite 初始化脚本
│   └── utils/               # 日志等工具
├── lib/                     # 企业微信 SDK 动态库
├── data/                    # SQLite 数据和运行时数据
├── Dockerfile
├── docker-compose.yml
├── docker-deploy.sh
└── .env.example
```

## 运行前准备

你至少需要准备以下配置：

- 企业微信消息存档能力，以及对应 `CorpID`、`Secret`、回调 `Token`、`EncodingAESKey`
- 对应的私钥文件，默认路径是 `private_key.pem`
- 至少一个可写的 Craft 文档链接、文档 ID 和访问 token
- 如果要处理图片/视频/文件，建议配置腾讯云 COS

## 快速开始

### 1. 配置环境变量

复制配置模板：

```bash
cp .env.example .env
```

然后按实际环境填写 `.env`。

### 2. 使用 Docker 启动

```bash
./docker-deploy.sh
```

服务默认监听 `8001` 端口，启动后可检查：

```bash
curl http://localhost:8001/
```

查看日志：

```bash
docker logs -f craftsaver
```

### 3. 本地直接运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8001
```

本地运行时同样需要：

- `.env` 配置完整
- `private_key.pem` 可读
- `lib/` 下存在当前平台可用的企业微信 SDK 动态库

## 创建用户绑定

每个企微用户都要先绑定一个 Craft 文档，否则消息不会被转发。

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

创建绑定时服务会先验证 Craft 文档是否可访问，验证失败会直接返回错误。

## API 概览

### 基础接口

- `GET /`：服务健康检查
- `GET /scalar`：API 文档
- `GET /openapi.json`：OpenAPI 描述

### 企业微信

- `POST /wecom/callback`：企业微信回调入口，同时触发消息拉取和处理

### 绑定管理

- `GET /bindings`：获取全部绑定
- `GET /bindings/{openid}`：查询单个绑定
- `POST /bindings`：创建或覆盖绑定
- `PUT /bindings/{openid}`：更新绑定
- `DELETE /bindings/{openid}`：删除绑定
- `POST /bindings/verify`：验证 Craft 文档访问权限

### Craft

- `POST /craft/save`：手动写入一条消息到 Craft

## 环境变量

| 变量 | 必需 | 说明 | 默认值 |
| --- | --- | --- | --- |
| `WECOM_TOKEN` | 是 | 企业微信回调 Token | - |
| `WECOM_CORP_ID` | 是 | 企业微信企业 ID | - |
| `WECOM_ENCODING_AES_KEY` | 是 | 企业微信回调 AES Key | - |
| `WECOM_APP_SECRET` | 是 | 企业微信消息存档 Secret | - |
| `WECOM_PRIVATE_KEY_PATH` | 是 | 私钥文件路径 | `private_key.pem` |
| `WECOM_BOT_USERID` | 否 | 机器人 UserID，用于过滤自身消息 | - |
| `WECOM_OFFSET_MAX` | 否 | 首次或补拉时使用的最大偏移量 | `0` |
| `SQLITE_DB_PATH` | 否 | SQLite 文件路径 | `data/craftsaver.db` |
| `APP_PORT` | 否 | 服务端口 | `8001` |
| `LOG_LEVEL` | 否 | 日志级别 | `INFO` |
| `COS_SECRET_ID` | 否 | 腾讯云 COS SecretId | - |
| `COS_SECRET_KEY` | 否 | 腾讯云 COS SecretKey | - |
| `COS_REGION` | 否 | COS 区域 | `ap-shanghai` |
| `COS_BUCKET` | 否 | COS Bucket 名称 | - |
| `COS_BASE_URL` | 否 | COS 访问基础地址 | - |
| `COS_ROOT_DIR` | 否 | COS 根目录前缀 | - |
| `HOST_IMAGE_DIR` | 否 | Docker 映射到容器 `/app/images` 的宿主目录 | `./data/images` |
| `HOST_DATA_DIR` | 否 | Docker 映射到容器 `/app/data` 的宿主目录 | `./data` |

说明：

- `CRAFT_LINKS_ID` 不是全局运行配置，Craft 参数按用户绑定存入数据库。
- 不配置 COS 时，服务仍可启动，但媒体文件上传能力不可用。
- `APP_PORT` 在 `.env`、`docker-compose.yml` 和启动命令中应保持一致。

## 常用验证

部署或修改后，至少检查这几项：

```bash
curl http://localhost:8001/
curl http://localhost:8001/openapi.json
docker logs craftsaver --tail 200
```

如果使用 Docker：

```bash
docker compose ps
```

然后打开 `http://localhost:8001/scalar` 确认文档页面可访问。

## 常见问题

### 1. 服务能启动，但收不到消息

优先检查：

- 企业微信回调地址是否指向 `POST /wecom/callback`
- `WECOM_TOKEN` 和 `WECOM_ENCODING_AES_KEY` 是否正确
- `WECOM_APP_SECRET` 是否是消息存档 Secret，而不是别的应用 Secret
- `private_key.pem` 是否与企业微信消息存档配置匹配

### 2. 服务启动后日志提示 SDK 初始化失败

优先检查：

- `lib/` 下是否有当前平台对应的 `libWeWorkFinanceSdk_C.so`
- `WECOM_PRIVATE_KEY_PATH` 指向的文件是否存在
- `WECOM_CORP_ID`、`WECOM_APP_SECRET` 是否填写正确

### 3. 绑定创建失败

通常是 Craft 参数校验失败。检查：

- `craft_link_id`
- `craft_document_id`
- `craft_token`

可以直接调用 `POST /bindings/verify` 单独验证。

### 4. 图片或文件没有写入 Craft

优先检查：

- COS 配置是否完整
- 本地文件是否已成功下载到 `images/` 或挂载目录
- COS Bucket 权限和访问地址是否可用

## 许可证

MIT
