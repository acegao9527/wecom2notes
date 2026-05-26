# HTTP 目标配置

HTTP 目标使用 `target_type=http`，适合把统一消息推送到 webhook、自动化平台或自定义服务。

## 目标配置

```json
{
  "id": "webhook-main",
  "name": "Webhook Main",
  "target_type": "http",
  "config": {
    "url": "https://example.com/wecom2notes",
    "method": "POST",
    "headers": {
      "X-Webhook-Token": "secret"
    },
    "timeout": 30
  }
}
```

默认会发送 JSON：

```json
{
  "event": "wecom2notes.message",
  "target_id": "webhook-main",
  "route_id": "1",
  "message": {
    "msg_id": "message-id",
    "source": "wecom",
    "msg_type": "text",
    "content": "hello",
    "from_user": "user-id",
    "create_time": 1700000000,
    "raw_data": {},
    "attachments": []
  }
}
```

## 可选配置

- `method`：支持 `POST`、`PUT`、`PATCH`、`GET`，默认 `POST`。
- `headers`：随请求发送的 HTTP header。
- `bearer_token`：自动补充 `Authorization: Bearer ...`，不会覆盖已显式配置的 `Authorization`。
- `success_statuses`：自定义成功状态码数组，默认任意 `2xx`。
- `verify_url`：配置后，管理台验证目标时会请求这个 URL；不配置时只校验 URL 和 method。
- `verify_method`：`verify_url` 的请求方法，支持 `GET`、`HEAD`、`POST`，默认 `GET`。
- `extra`：附加到投递 JSON 根节点的对象。

投递状态可在 `GET /admin/deliveries` 查看。
