# Obsidian / Markdown 目标配置

Obsidian 目标基于 Markdown 文件系统写入。Docker 中建议把 vault 挂载到 `/notes`。

## 环境变量方式

```bash
OBSIDIAN_VAULT_PATH=/notes
OBSIDIAN_BASE_DIR=WeCom
OBSIDIAN_MODE=daily
```

支持模式：

- `daily`：写入 `WeCom/YYYY-MM-DD.md`
- `sender`：写入 `WeCom/People/{sender}.md`
- `chat`：写入 `WeCom/Chats/{chat}.md`

## API 配置方式

```bash
curl -X POST http://localhost:8001/admin/destinations \
  -H "Content-Type: application/json" \
  -d '{
    "id": "obsidian-local",
    "name": "Local Obsidian",
    "target_type": "obsidian",
    "config": {
      "root_path": "/notes",
      "base_dir": "WeCom",
      "mode": "daily",
      "link_style": "wiki"
    }
  }'
```

附件默认写入 `WeCom/assets/YYYY/MM/`。
