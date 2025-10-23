-- panDirectServer SQLite 数据库架构
-- 优化后的高性能数据存储方案

-- 1. 直链缓存表
CREATE TABLE IF NOT EXISTS direct_link_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,              -- 文件路径
    url TEXT NOT NULL,                      -- 直链URL
    expire_time INTEGER NOT NULL,           -- 过期时间戳
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
);

-- 直链缓存索引
CREATE INDEX IF NOT EXISTS idx_direct_link_path ON direct_link_cache(path);
CREATE INDEX IF NOT EXISTS idx_direct_link_expire ON direct_link_cache(expire_time);

-- 2. 路径ID缓存表
CREATE TABLE IF NOT EXISTS path_id_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,              -- 文件路径
    file_id TEXT NOT NULL,                  -- 文件ID
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
);

-- 路径ID缓存索引
CREATE INDEX IF NOT EXISTS idx_path_id_path ON path_id_cache(path);
CREATE INDEX IF NOT EXISTS idx_path_id_file_id ON path_id_cache(file_id);

-- 3. Item路径映射表（原 item_path_db.json）
CREATE TABLE IF NOT EXISTS item_path_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT UNIQUE NOT NULL,           -- Emby Item ID
    file_path TEXT NOT NULL,                -- 文件路径
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
);

-- Item路径映射索引
CREATE INDEX IF NOT EXISTS idx_item_path_item_id ON item_path_mapping(item_id);
CREATE INDEX IF NOT EXISTS idx_item_path_file_path ON item_path_mapping(file_path);

-- 4. 用户历史记录表
CREATE TABLE IF NOT EXISTS user_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,                  -- 用户ID
    device_id TEXT,                         -- 设备ID
    device_name TEXT,                       -- 设备名称
    client_name TEXT,                       -- 客户端名称
    ip_address TEXT,                        -- IP地址
    user_agent TEXT,                        -- 用户代理
    last_seen INTEGER NOT NULL,             -- 最后活跃时间戳
    created_at INTEGER DEFAULT (unixepoch())
);

-- 用户历史索引
CREATE INDEX IF NOT EXISTS idx_user_history_user_id ON user_history(user_id);
CREATE INDEX IF NOT EXISTS idx_user_history_device_id ON user_history(device_id);
CREATE INDEX IF NOT EXISTS idx_user_history_ip ON user_history(ip_address);
CREATE INDEX IF NOT EXISTS idx_user_history_last_seen ON user_history(last_seen);

-- 5. 客户端连接跟踪表
CREATE TABLE IF NOT EXISTS client_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id TEXT UNIQUE NOT NULL,     -- 连接ID
    user_id TEXT,                           -- 用户ID
    device_id TEXT,                         -- 设备ID
    device_name TEXT,                       -- 设备名称
    client_name TEXT,                       -- 客户端名称
    client_version TEXT,                    -- 客户端版本
    ip_address TEXT,                        -- IP地址
    user_agent TEXT,                        -- 用户代理
    status TEXT DEFAULT 'active',           -- 连接状态：active, inactive, blocked
    connected_at INTEGER NOT NULL,          -- 连接时间
    last_activity INTEGER NOT NULL,         -- 最后活跃时间
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
);

-- 客户端连接索引
CREATE INDEX IF NOT EXISTS idx_client_conn_id ON client_connections(connection_id);
CREATE INDEX IF NOT EXISTS idx_client_user_id ON client_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_client_device_id ON client_connections(device_id);
CREATE INDEX IF NOT EXISTS idx_client_ip ON client_connections(ip_address);
CREATE INDEX IF NOT EXISTS idx_client_status ON client_connections(status);
CREATE INDEX IF NOT EXISTS idx_client_last_activity ON client_connections(last_activity);

-- 6. 配置存储表（统一配置管理）
CREATE TABLE IF NOT EXISTS config_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT UNIQUE NOT NULL,        -- 配置键
    config_value TEXT NOT NULL,             -- 配置值（JSON）
    config_type TEXT DEFAULT 'json',        -- 配置类型
    description TEXT,                       -- 描述
    version INTEGER DEFAULT 1,              -- 配置版本
    created_at INTEGER DEFAULT (unixepoch()),
    updated_at INTEGER DEFAULT (unixepoch())
);

-- 配置存储索引
CREATE INDEX IF NOT EXISTS idx_config_key ON config_store(config_key);

-- 7. 配置分类表（更细粒度的配置管理）
CREATE TABLE IF NOT EXISTS config_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_name TEXT UNIQUE NOT NULL,      -- 配置段名（如emby, 123, service）
    section_config TEXT NOT NULL,           -- 配置段内容（JSON）
    enabled INTEGER DEFAULT 1,              -- 是否启用
    last_modified INTEGER DEFAULT (unixepoch()),
    created_at INTEGER DEFAULT (unixepoch())
);

-- 配置段索引
CREATE INDEX IF NOT EXISTS idx_config_section_name ON config_sections(section_name);
CREATE INDEX IF NOT EXISTS idx_config_section_enabled ON config_sections(enabled);

-- 8. 文件搜索缓存表（优化123网盘搜索）
CREATE TABLE IF NOT EXISTS file_search_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,                 -- 文件名
    file_id TEXT NOT NULL,                  -- 文件ID
    file_size INTEGER,                      -- 文件大小
    parent_id TEXT,                         -- 父目录ID
    full_path TEXT,                         -- 完整路径
    created_time TEXT,                      -- 文件创建时间
    cached_at INTEGER DEFAULT (unixepoch()),
    expire_time INTEGER NOT NULL            -- 缓存过期时间
);

-- 文件搜索缓存索引
CREATE INDEX IF NOT EXISTS idx_search_filename ON file_search_cache(filename);
CREATE INDEX IF NOT EXISTS idx_search_file_id ON file_search_cache(file_id);
CREATE INDEX IF NOT EXISTS idx_search_expire ON file_search_cache(expire_time);
CREATE INDEX IF NOT EXISTS idx_search_full_path ON file_search_cache(full_path);

-- 9. API调用统计表（性能监控）
CREATE TABLE IF NOT EXISTS api_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_endpoint TEXT NOT NULL,             -- API端点
    method TEXT NOT NULL,                   -- HTTP方法
    response_time_ms INTEGER,               -- 响应时间（毫秒）
    status_code INTEGER,                    -- HTTP状态码
    user_id TEXT,                           -- 用户ID
    ip_address TEXT,                        -- IP地址
    created_at INTEGER DEFAULT (unixepoch())
);

-- API统计索引
CREATE INDEX IF NOT EXISTS idx_api_stats_endpoint ON api_stats(api_endpoint);
CREATE INDEX IF NOT EXISTS idx_api_stats_created ON api_stats(created_at);
CREATE INDEX IF NOT EXISTS idx_api_stats_user ON api_stats(user_id);

-- 数据清理触发器（自动删除过期数据）

-- 清理过期的直链缓存
CREATE TRIGGER IF NOT EXISTS cleanup_expired_direct_links
    AFTER INSERT ON direct_link_cache
    WHEN NEW.expire_time < unixepoch()
BEGIN
    DELETE FROM direct_link_cache WHERE expire_time < unixepoch();
END;

-- 清理过期的文件搜索缓存
CREATE TRIGGER IF NOT EXISTS cleanup_expired_search_cache
    AFTER INSERT ON file_search_cache
    WHEN NEW.expire_time < unixepoch()
BEGIN
    DELETE FROM file_search_cache WHERE expire_time < unixepoch();
END;

-- 限制API统计表大小（只保留最近7天）
CREATE TRIGGER IF NOT EXISTS cleanup_old_api_stats
    AFTER INSERT ON api_stats
    WHEN NEW.created_at > unixepoch() - 604800  -- 7天
BEGIN
    DELETE FROM api_stats WHERE created_at < unixepoch() - 604800;
END;

-- 视图：活跃连接
CREATE VIEW IF NOT EXISTS active_connections AS
SELECT 
    connection_id,
    user_id,
    device_name,
    client_name,
    ip_address,
    connected_at,
    last_activity,
    (unixepoch() - last_activity) as idle_seconds
FROM client_connections 
WHERE status = 'active' 
    AND last_activity > unixepoch() - 3600  -- 1小时内活跃
ORDER BY last_activity DESC;

-- 视图：缓存统计
CREATE VIEW IF NOT EXISTS cache_stats AS
SELECT 
    'direct_links' as cache_type,
    COUNT(*) as total_count,
    COUNT(CASE WHEN expire_time > unixepoch() THEN 1 END) as valid_count,
    COUNT(CASE WHEN expire_time <= unixepoch() THEN 1 END) as expired_count
FROM direct_link_cache
UNION ALL
SELECT 
    'path_ids' as cache_type,
    COUNT(*) as total_count,
    COUNT(*) as valid_count,
    0 as expired_count
FROM path_id_cache
UNION ALL
SELECT 
    'item_paths' as cache_type,
    COUNT(*) as total_count,
    COUNT(*) as valid_count,
    0 as expired_count
FROM item_path_mapping
UNION ALL
SELECT 
    'file_search' as cache_type,
    COUNT(*) as total_count,
    COUNT(CASE WHEN expire_time > unixepoch() THEN 1 END) as valid_count,
    COUNT(CASE WHEN expire_time <= unixepoch() THEN 1 END) as expired_count
FROM file_search_cache;

-- 初始化完成标记
INSERT OR IGNORE INTO config_store (config_key, config_value, description) 
VALUES ('db_version', '1.0.0', 'Database schema version');

INSERT OR IGNORE INTO config_store (config_key, config_value, description) 
VALUES ('db_created_at', json_quote(unixepoch()), 'Database creation timestamp');

-- 数据库优化配置
PRAGMA journal_mode = WAL;          -- WAL模式，提升并发性能
PRAGMA synchronous = NORMAL;        -- 平衡安全性和性能
PRAGMA temp_store = MEMORY;         -- 临时表使用内存
PRAGMA mmap_size = 268435456;       -- 256MB内存映射
PRAGMA cache_size = 10000;          -- 缓存页数
PRAGMA optimize;                    -- 自动优化
