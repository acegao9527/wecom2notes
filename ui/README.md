# wecom2notes 管理台

这个目录是内置管理端的静态前端，可由 FastAPI 挂载到 `/admin/ui`：

- `index.html`：跳转到管理台主页面。
- `admin-console.html`：管理台页面骨架。
- `admin-console.css`：管理台样式。
- `admin-console.js`：管理台交互逻辑和 API 调用。

## 已覆盖功能

- 总览：健康状态、metrics、当前 seq、处理链路。
- 目标管理：Craft、Obsidian、Markdown、Logseq、Notion、WebDAV、Git、HTTP 目标的新增、编辑、删除、启停和验证。
- 路由规则：source、from_user、chat_id、msg_type、keyword 到 destination 的新增、编辑、删除、启停和测试命中。
- 投递队列：failed、pending、delivered 状态筛选与重放入口。
- 消息审计：统一消息、附件、原始 JSON 和投递结果。
- Craft 绑定：兼容旧版用户绑定，支持新增、编辑、删除、启停和验证。
- 管理鉴权：配置 `ADMIN_TOKEN` 后，前端通过 `X-Admin-Token` 调用管理 API。

## 接口映射

- `GET /admin/session`
- `GET /admin/overview`
- `GET /health`
- `GET /metrics`
- `GET /admin/target-types`
- `GET /admin/destinations`
- `POST /admin/destinations`
- `PUT /admin/destinations/{destination_id}`
- `PATCH /admin/destinations/{destination_id}/enabled`
- `DELETE /admin/destinations/{destination_id}`
- `POST /admin/destinations/{destination_id}/verify`
- `GET /admin/routes`
- `POST /admin/routes`
- `PUT /admin/routes/{route_id}`
- `PATCH /admin/routes/{route_id}/enabled`
- `DELETE /admin/routes/{route_id}`
- `POST /admin/routes/test`
- `GET /admin/deliveries`
- `GET /admin/messages`
- `GET /admin/messages/{source}/{msg_id}`
- `POST /admin/replay`
- `GET /bindings`
- `POST /bindings`
- `PUT /bindings/{openid}`
- `PATCH /bindings/{openid}/enabled`
- `DELETE /bindings/{openid}`
- `POST /bindings/verify`
