# 发布检查清单

- [ ] README 快速开始可从空环境跑通。
- [ ] `.env.example` 不包含真实 token、secret、bucket、私钥路径之外的敏感内容。
- [ ] `python3 -m unittest` 通过。
- [ ] `python3 -m compileall -q main.py src` 通过。
- [ ] Docker build 成功。
- [ ] `curl /`、`curl /openapi.json`、`curl /metrics` 正常。
- [ ] `docker logs wecom2notes --tail 200` 没有新的 traceback。
- [ ] GitHub Actions 通过。
- [ ] release note 写清楚数据库迁移和默认数据库名变化。
