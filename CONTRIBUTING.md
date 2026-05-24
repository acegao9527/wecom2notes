# 贡献指南

## 开发流程

- 新功能优先以 source connector、target adapter、storage backend 或 router rule 的形式添加。
- 修改消息解析、投递状态、数据库结构时必须补测试。
- 不要提交 `.env`、私钥、数据库、真实 token 或本地笔记库内容。
- 修改代码后本地至少执行：

```bash
python3 -m unittest discover -s tests
python3 -m compileall -q main.py src
./docker-deploy.sh
curl http://localhost:8001/
curl http://localhost:8001/openapi.json
docker logs wecom2notes --tail 200
docker compose down
```

## Adapter 规范

新的笔记目标应实现 `src.core.interfaces.TargetAdapter`：

- `verify()` 验证目标配置。
- `deliver()` 投递一条 `UnifiedMessage`。
- 返回 `DeliveryResult`，不要直接吞掉错误。
- 不要在 adapter 内读取企业微信配置，source 与 target 必须解耦。

## Source 规范

新的消息源应实现 `src.core.interfaces.SourceConnector`，输出统一的 `UnifiedMessage`。附件统一填入 `AttachmentInfo`。
