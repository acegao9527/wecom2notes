# 部署

## Docker Compose

```bash
cp .env.example .env
./docker-deploy.sh
curl http://localhost:8001/
```

默认挂载：

- `./data` -> `/app/data`
- `./data/images` -> `/app/images`
- `./data/notes` -> `/notes`
- `./lib` -> `/app/lib`
- `./private_key.pem` -> `/app/private_key.pem`

## 生产环境

- 不要把 `.env` 和私钥打进镜像。
- 使用 volume、secret manager 或部署平台的环境变量注入敏感配置。
- 生产 Linux x86_64 使用 `lib/wework-x86_64/libWeWorkFinanceSdk_C.so`。

## 验证

```bash
curl http://localhost:8001/
curl http://localhost:8001/openapi.json
curl http://localhost:8001/metrics
docker logs wecom2notes --tail 200
```
