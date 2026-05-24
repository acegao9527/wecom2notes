# 企业微信配置

## 必需配置

- `WECOM_TOKEN`：回调 Token。
- `WECOM_CORP_ID`：企业 ID。
- `WECOM_ENCODING_AES_KEY`：回调 AES Key。
- `WECOM_APP_SECRET`：会话内容存档 Secret。
- `WECOM_PRIVATE_KEY_PATH`：私钥路径，Docker 默认挂载到 `/app/private_key.pem`。

## 运行说明

服务使用企业微信会话内容存档 SDK 拉取消息，通过 `source_cursors` 表和 `/app/data/.wecom_seq` 保存游标。

公网回调地址指向：

```text
POST /wecom/callback
GET /wecom/callback
```

`GET /wecom/callback` 用于企业微信 URL 验证，`POST /wecom/callback` 会触发消息归档拉取和投递。

## 本地开发

Mac 不能直接加载 Linux x86_64 SDK。可设置：

```bash
WECOM_DISABLE_SDK=true
```

如需完整 SDK 验证，使用 Docker 容器运行。
