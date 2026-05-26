# Craft 目标配置

Craft 目标使用 `target_type=craft`。

## 目标配置

```json
{
  "id": "craft-main",
  "name": "Craft Main",
  "target_type": "craft",
  "config": {
    "link_id": "your-link-id",
    "document_id": "your-document-id",
    "token": "pdk_xxx"
  }
}
```

也可以继续使用兼容的用户绑定接口：

```bash
curl -X POST http://localhost:8001/bindings \
  -H "Content-Type: application/json" \
  -d '{
    "wecom_openid": "user-id",
    "craft_link_id": "link-id",
    "craft_document_id": "document-id",
    "craft_token": "pdk_xxx"
  }'
```

服务启动时会扫描旧版 `user_mappings` 绑定，并为每个绑定补齐一个 `craft:{wecom_openid}` 投递目标和一条按 `from_user` 匹配的路由。这个迁移是幂等的，只创建缺失项，不覆盖已经在管理台里调整过的目标或路由。

投递状态可在 `GET /admin/deliveries` 查看。
