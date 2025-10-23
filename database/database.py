#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import json
import logging
import threading
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class DatabaseManager:
    """SQLite 数据库管理器 - 高性能版本"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器
        
        :param db_path: 数据库文件路径，默认为 config/pandirect.db
        """
        if db_path is None:
            db_path = os.path.join('config', 'pandirect.db')
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 连接池设置
        self._local = threading.local()
        self._lock = threading.Lock()
        
        # 初始化数据库
        self.initialize_database()
        
        logger.info(f"✅ SQLite 数据库初始化完成: {self.db_path}")

    def initialize_database(self):
        """初始化数据库架构"""
        try:
            # 读取schema文件
            schema_file = Path(__file__).parent / 'schema.sql'
            if not schema_file.exists():
                logger.error(f"❌ 数据库架构文件不存在: {schema_file}")
                return
            
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # 执行架构初始化
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
                conn.commit()
            
            logger.info("✅ 数据库架构初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            raise

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接（线程安全）"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False
            )
            # 设置行工厂，返回字典格式结果
            self._local.connection.row_factory = sqlite3.Row
            
            # 性能优化配置
            self._local.connection.execute("PRAGMA journal_mode = WAL")
            self._local.connection.execute("PRAGMA synchronous = NORMAL")
            self._local.connection.execute("PRAGMA temp_store = MEMORY")
            self._local.connection.execute("PRAGMA mmap_size = 268435456")  # 256MB
            self._local.connection.execute("PRAGMA cache_size = 10000")
            
        return self._local.connection

    @contextmanager
    def get_cursor(self):
        """获取数据库游标（上下文管理器）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def close_connection(self):
        """关闭当前线程的数据库连接"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    # ==================== 直链缓存操作 ====================

    def get_direct_link(self, path: str) -> Optional[Dict[str, Any]]:
        """获取直链缓存"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    "SELECT url, expire_time, created_at FROM direct_link_cache WHERE path = ? AND expire_time > ?",
                    (path, int(time.time()))
                )
                row = cursor.fetchone()
                if row:
                    return {
                        'url': row['url'],
                        'expire_time': row['expire_time'],
                        'created_at': row['created_at']
                    }
                return None
        except Exception as e:
            logger.error(f"❌ 获取直链缓存失败: {e}")
            return None

    def set_direct_link(self, path: str, url: str, expire_seconds: int = 3600) -> bool:
        """设置直链缓存"""
        try:
            expire_time = int(time.time()) + expire_seconds
            with self.get_cursor() as cursor:
                cursor.execute(
                    """INSERT OR REPLACE INTO direct_link_cache 
                       (path, url, expire_time, updated_at) VALUES (?, ?, ?, ?)""",
                    (path, url, expire_time, int(time.time()))
                )
                return True
        except Exception as e:
            logger.error(f"❌ 设置直链缓存失败: {e}")
            return False

    def clear_expired_direct_links(self) -> int:
        """清理过期的直链缓存"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("DELETE FROM direct_link_cache WHERE expire_time <= ?", (int(time.time()),))
                return cursor.rowcount
        except Exception as e:
            logger.error(f"❌ 清理过期直链失败: {e}")
            return 0

    # ==================== 路径ID缓存操作 ====================

    def get_path_id(self, path: str) -> Optional[str]:
        """获取路径对应的文件ID"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT file_id FROM path_id_cache WHERE path = ?", (path,))
                row = cursor.fetchone()
                return row['file_id'] if row else None
        except Exception as e:
            logger.error(f"❌ 获取路径ID失败: {e}")
            return None

    def set_path_id(self, path: str, file_id: str) -> bool:
        """设置路径对应的文件ID"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    """INSERT OR REPLACE INTO path_id_cache 
                       (path, file_id, updated_at) VALUES (?, ?, ?)""",
                    (path, file_id, int(time.time()))
                )
                return True
        except Exception as e:
            logger.error(f"❌ 设置路径ID失败: {e}")
            return False

    def get_all_path_ids(self) -> Dict[str, str]:
        """获取所有路径ID映射"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT path, file_id FROM path_id_cache")
                rows = cursor.fetchall()
                return {row['path']: row['file_id'] for row in rows}
        except Exception as e:
            logger.error(f"❌ 获取所有路径ID失败: {e}")
            return {}

    # ==================== Item路径映射操作 ====================

    def get_item_path(self, item_id: str) -> Optional[str]:
        """获取Item对应的文件路径"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT file_path FROM item_path_mapping WHERE item_id = ?", (str(item_id),))
                row = cursor.fetchone()
                return row['file_path'] if row else None
        except Exception as e:
            logger.error(f"❌ 获取Item路径失败: {e}")
            return None

    def set_item_path(self, item_id: str, file_path: str) -> bool:
        """设置Item对应的文件路径"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    """INSERT OR REPLACE INTO item_path_mapping 
                       (item_id, file_path, updated_at) VALUES (?, ?, ?)""",
                    (str(item_id), file_path, int(time.time()))
                )
                return True
        except Exception as e:
            logger.error(f"❌ 设置Item路径失败: {e}")
            return False

    def has_item_path(self, item_id: str) -> bool:
        """检查Item路径是否存在"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1 FROM item_path_mapping WHERE item_id = ?", (str(item_id),))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"❌ 检查Item路径失败: {e}")
            return False

    def remove_item_path(self, item_id: str) -> bool:
        """删除Item路径映射"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("DELETE FROM item_path_mapping WHERE item_id = ?", (str(item_id),))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"❌ 删除Item路径失败: {e}")
            return False

    def get_item_path_stats(self) -> Dict[str, Any]:
        """获取Item路径映射统计"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as total FROM item_path_mapping")
                total = cursor.fetchone()['total']
                
                # 计算数据库文件大小
                db_size = os.path.getsize(self.db_path) if self.db_path.exists() else 0
                
                return {
                    'total': total,
                    'size': db_size
                }
        except Exception as e:
            logger.error(f"❌ 获取Item路径统计失败: {e}")
            return {'total': 0, 'size': 0}

    # ==================== 用户历史记录操作 ====================

    def add_user_activity(self, user_id: str, device_id: str = None, device_name: str = None,
                         client_name: str = None, ip_address: str = None, user_agent: str = None) -> bool:
        """添加用户活动记录"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    """INSERT INTO user_history 
                       (user_id, device_id, device_name, client_name, ip_address, user_agent, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, device_id, device_name, client_name, ip_address, user_agent, int(time.time()))
                )
                return True
        except Exception as e:
            logger.error(f"❌ 添加用户活动失败: {e}")
            return False

    def get_user_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户历史记录"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    """SELECT user_id, device_id, device_name, client_name, ip_address, 
                              user_agent, last_seen, created_at
                       FROM user_history 
                       ORDER BY last_seen DESC 
                       LIMIT ?""",
                    (limit,)
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ 获取用户历史失败: {e}")
            return []

    def get_unique_users(self) -> Dict[str, Dict[str, Any]]:
        """获取去重的用户列表"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    """SELECT user_id, 
                              GROUP_CONCAT(DISTINCT device_name) as devices,
                              GROUP_CONCAT(DISTINCT ip_address) as ips,
                              MAX(last_seen) as last_seen,
                              COUNT(*) as activity_count
                       FROM user_history 
                       GROUP BY user_id
                       ORDER BY last_seen DESC"""
                )
                rows = cursor.fetchall()
                
                result = {}
                for row in rows:
                    result[row['user_id']] = {
                        'devices': row['devices'].split(',') if row['devices'] else [],
                        'ips': row['ips'].split(',') if row['ips'] else [],
                        'last_seen': row['last_seen'],
                        'activity_count': row['activity_count']
                    }
                
                return result
        except Exception as e:
            logger.error(f"❌ 获取用户列表失败: {e}")
            return {}

    # ==================== 客户端连接跟踪 ====================

    def add_client_connection(self, connection_id: str, user_id: str = None, device_id: str = None,
                             device_name: str = None, client_name: str = None, client_version: str = None,
                             ip_address: str = None, user_agent: str = None) -> bool:
        """添加客户端连接"""
        try:
            current_time = int(time.time())
            with self.get_cursor() as cursor:
                cursor.execute(
                    """INSERT OR REPLACE INTO client_connections 
                       (connection_id, user_id, device_id, device_name, client_name, client_version,
                        ip_address, user_agent, status, connected_at, last_activity, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                    (connection_id, user_id, device_id, device_name, client_name, client_version,
                     ip_address, user_agent, current_time, current_time, current_time)
                )
                return True
        except Exception as e:
            logger.error(f"❌ 添加客户端连接失败: {e}")
            return False

    def update_client_activity(self, connection_id: str) -> bool:
        """更新客户端活动时间"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    "UPDATE client_connections SET last_activity = ?, updated_at = ? WHERE connection_id = ?",
                    (int(time.time()), int(time.time()), connection_id)
                )
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"❌ 更新客户端活动失败: {e}")
            return False

    def get_active_connections(self, timeout_seconds: int = 3600) -> Dict[str, Dict[str, Any]]:
        """获取活跃连接"""
        try:
            cutoff_time = int(time.time()) - timeout_seconds
            with self.get_cursor() as cursor:
                cursor.execute(
                    """SELECT connection_id, user_id, device_id, device_name, client_name, client_version,
                              ip_address, user_agent, connected_at, last_activity
                       FROM client_connections 
                       WHERE status = 'active' AND last_activity > ?
                       ORDER BY last_activity DESC""",
                    (cutoff_time,)
                )
                rows = cursor.fetchall()
                
                result = {}
                for row in rows:
                    result[row['connection_id']] = dict(row)
                
                return result
        except Exception as e:
            logger.error(f"❌ 获取活跃连接失败: {e}")
            return {}

    def cleanup_expired_connections(self, timeout_seconds: int = 3600) -> int:
        """清理过期的连接"""
        try:
            cutoff_time = int(time.time()) - timeout_seconds
            with self.get_cursor() as cursor:
                cursor.execute(
                    "UPDATE client_connections SET status = 'inactive' WHERE last_activity <= ? AND status = 'active'",
                    (cutoff_time,)
                )
                return cursor.rowcount
        except Exception as e:
            logger.error(f"❌ 清理过期连接失败: {e}")
            return 0

    # ==================== 文件搜索缓存 ====================

    def get_file_search_cache(self, filename: str) -> Optional[Dict[str, Any]]:
        """获取文件搜索缓存"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    """SELECT file_id, file_size, parent_id, full_path, created_time, cached_at
                       FROM file_search_cache 
                       WHERE filename = ? AND expire_time > ?""",
                    (filename, int(time.time()))
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ 获取文件搜索缓存失败: {e}")
            return None

    def set_file_search_cache(self, filename: str, file_id: str, file_size: int = None,
                             parent_id: str = None, full_path: str = None, created_time: str = None,
                             expire_seconds: int = 3600) -> bool:
        """设置文件搜索缓存"""
        try:
            expire_time = int(time.time()) + expire_seconds
            with self.get_cursor() as cursor:
                cursor.execute(
                    """INSERT OR REPLACE INTO file_search_cache 
                       (filename, file_id, file_size, parent_id, full_path, created_time, expire_time)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (filename, file_id, file_size, parent_id, full_path, created_time, expire_time)
                )
                return True
        except Exception as e:
            logger.error(f"❌ 设置文件搜索缓存失败: {e}")
            return False

    # ==================== 配置存储操作 ====================

    def get_config_section(self, section_name: str) -> Optional[Dict[str, Any]]:
        """获取配置段"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    "SELECT section_config FROM config_sections WHERE section_name = ? AND enabled = 1",
                    (section_name,)
                )
                row = cursor.fetchone()
                if row:
                    return json.loads(row['section_config'])
                return None
        except Exception as e:
            logger.error(f"❌ 获取配置段失败: {section_name}, {e}")
            return None

    def set_config_section(self, section_name: str, config_data: Dict[str, Any]) -> bool:
        """设置配置段"""
        try:
            config_json = json.dumps(config_data, ensure_ascii=False)
            with self.get_cursor() as cursor:
                cursor.execute(
                    """INSERT OR REPLACE INTO config_sections 
                       (section_name, section_config, last_modified) VALUES (?, ?, ?)""",
                    (section_name, config_json, int(time.time()))
                )
                return True
        except Exception as e:
            logger.error(f"❌ 设置配置段失败: {section_name}, {e}")
            return False

    def get_all_config_sections(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置段"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    "SELECT section_name, section_config FROM config_sections WHERE enabled = 1"
                )
                rows = cursor.fetchall()
                
                result = {}
                for row in rows:
                    try:
                        result[row['section_name']] = json.loads(row['section_config'])
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ 解析配置段JSON失败: {row['section_name']}, {e}")
                
                return result
        except Exception as e:
            logger.error(f"❌ 获取所有配置段失败: {e}")
            return {}

    def delete_config_section(self, section_name: str) -> bool:
        """删除配置段"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    "UPDATE config_sections SET enabled = 0 WHERE section_name = ?",
                    (section_name,)
                )
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"❌ 删除配置段失败: {section_name}, {e}")
            return False

    def get_config_value(self, config_key: str) -> Optional[str]:
        """获取单个配置值"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    "SELECT config_value FROM config_store WHERE config_key = ?",
                    (config_key,)
                )
                row = cursor.fetchone()
                return row['config_value'] if row else None
        except Exception as e:
            logger.error(f"❌ 获取配置值失败: {config_key}, {e}")
            return None

    def set_config_value(self, config_key: str, config_value: str, 
                        description: str = None) -> bool:
        """设置单个配置值"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    """INSERT OR REPLACE INTO config_store 
                       (config_key, config_value, description, updated_at) VALUES (?, ?, ?, ?)""",
                    (config_key, config_value, description, int(time.time()))
                )
                return True
        except Exception as e:
            logger.error(f"❌ 设置配置值失败: {config_key}, {e}")
            return False

    def list_config_keys(self) -> List[str]:
        """列出所有配置键"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT config_key FROM config_store")
                rows = cursor.fetchall()
                return [row['config_key'] for row in rows]
        except Exception as e:
            logger.error(f"❌ 列出配置键失败: {e}")
            return []

    # ==================== 统计和监控 ====================

    def add_api_stat(self, endpoint: str, method: str, response_time_ms: int,
                     status_code: int, user_id: str = None, ip_address: str = None) -> bool:
        """添加API调用统计"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(
                    """INSERT INTO api_stats 
                       (api_endpoint, method, response_time_ms, status_code, user_id, ip_address)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (endpoint, method, response_time_ms, status_code, user_id, ip_address)
                )
                return True
        except Exception as e:
            logger.error(f"❌ 添加API统计失败: {e}")
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT * FROM cache_stats")
                rows = cursor.fetchall()
                
                result = {}
                for row in rows:
                    result[row['cache_type']] = {
                        'total_count': row['total_count'],
                        'valid_count': row['valid_count'],
                        'expired_count': row['expired_count']
                    }
                
                return result
        except Exception as e:
            logger.error(f"❌ 获取缓存统计失败: {e}")
            return {}

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        try:
            with self.get_cursor() as cursor:
                # API响应时间统计
                cursor.execute(
                    """SELECT api_endpoint, 
                              COUNT(*) as call_count,
                              AVG(response_time_ms) as avg_response_time,
                              MIN(response_time_ms) as min_response_time,
                              MAX(response_time_ms) as max_response_time
                       FROM api_stats 
                       WHERE created_at > ? 
                       GROUP BY api_endpoint
                       ORDER BY call_count DESC""",
                    (int(time.time()) - 86400,)  # 最近24小时
                )
                api_stats = [dict(row) for row in cursor.fetchall()]
                
                # 数据库大小
                db_size = os.path.getsize(self.db_path) if self.db_path.exists() else 0
                
                return {
                    'api_stats': api_stats,
                    'database_size': db_size,
                    'cache_stats': self.get_cache_stats()
                }
        except Exception as e:
            logger.error(f"❌ 获取性能统计失败: {e}")
            return {}

    # ==================== 数据清理 ====================

    def clear_all_cache(self) -> Dict[str, int]:
        """清除所有缓存"""
        try:
            result = {}
            with self.get_cursor() as cursor:
                # 清除直链缓存
                cursor.execute("SELECT COUNT(*) as count FROM direct_link_cache")
                result['direct_links'] = cursor.fetchone()['count']
                cursor.execute("DELETE FROM direct_link_cache")
                
                # 清除路径ID缓存
                cursor.execute("SELECT COUNT(*) as count FROM path_id_cache")
                result['path_ids'] = cursor.fetchone()['count']
                cursor.execute("DELETE FROM path_id_cache")
                
                # 清除文件搜索缓存
                cursor.execute("SELECT COUNT(*) as count FROM file_search_cache")
                result['file_search'] = cursor.fetchone()['count']
                cursor.execute("DELETE FROM file_search_cache")
                
                # 不清除Item路径映射，这是永久数据
                
                logger.info(f"🧹 已清除所有缓存: {result}")
                return result
        except Exception as e:
            logger.error(f"❌ 清除缓存失败: {e}")
            return {}

    def vacuum_database(self) -> bool:
        """优化数据库（回收空间）"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("VACUUM")
                cursor.execute("PRAGMA optimize")
                logger.info("🔧 数据库优化完成")
                return True
        except Exception as e:
            logger.error(f"❌ 数据库优化失败: {e}")
            return False


# 全局数据库管理器实例
db_manager = None

def get_db_manager() -> DatabaseManager:
    """获取数据库管理器单例"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager

def init_database(db_path: str = None):
    """初始化数据库"""
    global db_manager
    db_manager = DatabaseManager(db_path)
    return db_manager
