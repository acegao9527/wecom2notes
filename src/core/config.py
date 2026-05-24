"""运行时配置加载。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


def load_route_config() -> Dict[str, Any]:
    """加载可选的 JSON 路由配置。"""
    path = Path(os.getenv("NOTES_ROUTES_CONFIG", "config/routes.json"))
    if not path.exists():
        return {"destinations": [], "routes": []}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "destinations": data.get("destinations", []),
        "routes": data.get("routes", []),
    }


def env_destinations() -> List[Dict[str, Any]]:
    """从环境变量生成内置目标。"""
    destinations: List[Dict[str, Any]] = []
    if os.getenv("OBSIDIAN_VAULT_PATH"):
        destinations.append(
            {
                "id": "env-obsidian",
                "name": "Env Obsidian Vault",
                "target_type": "obsidian",
                "config": {
                    "root_path": os.getenv("OBSIDIAN_VAULT_PATH"),
                    "base_dir": os.getenv("OBSIDIAN_BASE_DIR", "WeCom"),
                    "mode": os.getenv("OBSIDIAN_MODE", "daily"),
                    "link_style": "wiki",
                },
            }
        )
    if os.getenv("MARKDOWN_NOTES_PATH"):
        destinations.append(
            {
                "id": "env-markdown",
                "name": "Env Markdown Notes",
                "target_type": "markdown",
                "config": {
                    "root_path": os.getenv("MARKDOWN_NOTES_PATH"),
                    "base_dir": os.getenv("MARKDOWN_BASE_DIR", "WeCom"),
                    "mode": os.getenv("MARKDOWN_MODE", "daily"),
                },
            }
        )
    return destinations
