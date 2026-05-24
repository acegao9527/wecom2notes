CREATE TABLE IF NOT EXISTS unified_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id TEXT NOT NULL,
    source TEXT NOT NULL,
    msg_type TEXT,
    from_user TEXT,
    content TEXT,
    raw_data TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_unified_msg_id ON unified_messages(msg_id);
CREATE INDEX IF NOT EXISTS idx_unified_source ON unified_messages(source);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unified_source_msg_id ON unified_messages(source, msg_id);
