CREATE TABLE IF NOT EXISTS unified_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id TEXT NOT NULL,
    source TEXT NOT NULL,
    msg_type TEXT,
    from_user TEXT,
    content TEXT,
    raw_data TEXT,
    created_at TEXT,
    chat_id TEXT,
    to_user TEXT,
    sender_name TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_unified_source_msg_id ON unified_messages(source, msg_id);
CREATE INDEX IF NOT EXISTS idx_unified_msg_id ON unified_messages(msg_id);
CREATE INDEX IF NOT EXISTS idx_unified_source ON unified_messages(source);
CREATE INDEX IF NOT EXISTS idx_unified_from_user ON unified_messages(from_user);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    msg_id TEXT NOT NULL,
    file_name TEXT,
    local_path TEXT,
    content_type TEXT,
    size INTEGER,
    sha256 TEXT,
    url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attachments_msg ON attachments(source, msg_id);

CREATE TABLE IF NOT EXISTS source_cursors (
    source TEXT PRIMARY KEY,
    cursor_value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS destinations (
    id TEXT PRIMARY KEY,
    workspace_id TEXT DEFAULT 'default',
    name TEXT NOT NULL,
    target_type TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    is_enabled INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    workspace_id TEXT DEFAULT 'default',
    source TEXT DEFAULT 'wecom',
    from_user TEXT,
    chat_id TEXT,
    msg_type TEXT,
    keyword TEXT,
    destination_id TEXT NOT NULL,
    template TEXT,
    is_enabled INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(destination_id) REFERENCES destinations(id)
);

CREATE INDEX IF NOT EXISTS idx_routes_destination ON routes(destination_id);
CREATE INDEX IF NOT EXISTS idx_routes_source ON routes(source);

CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    msg_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    workspace_id TEXT DEFAULT 'default',
    target_type TEXT NOT NULL,
    route_id TEXT,
    status TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    error TEXT,
    external_id TEXT,
    metadata_json TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    delivered_at DATETIME,
    UNIQUE(source, msg_id, target_id)
);

CREATE INDEX IF NOT EXISTS idx_deliveries_status ON deliveries(status);
CREATE INDEX IF NOT EXISTS idx_deliveries_msg ON deliveries(source, msg_id);

CREATE TABLE IF NOT EXISTS user_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wecom_openid VARCHAR(128) NOT NULL,
    craft_link_id VARCHAR(128) NOT NULL,
    craft_document_id VARCHAR(128) NOT NULL,
    craft_token VARCHAR(128) NOT NULL,
    display_name VARCHAR(128),
    is_enabled INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(wecom_openid)
);

CREATE INDEX IF NOT EXISTS idx_wecom_openid ON user_mappings(wecom_openid);
