#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
标准关系型数据库配置管理器
每个配置项都有独立的字段，不使用JSON存储
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from database.database import get_db_manager

logger = logging.getLogger(__name__)

class StandardConfigManager:
    """标准关系型配置管理器"""

    def __init__(self):
        self.db = get_db_manager()
        self.ensure_config_tables()

    def ensure_config_tables(self):
        """确保配置表存在"""
        try:
            # 直接在代码中定义表结构，避免文件路径问题
            schema_sql = """
            -- 服务配置表
            CREATE TABLE IF NOT EXISTS service_config (
                id INTEGER PRIMARY KEY DEFAULT 1,
                port INTEGER NOT NULL DEFAULT 5245,
                host TEXT NOT NULL DEFAULT '0.0.0.0',
                external_url TEXT DEFAULT '',
                token TEXT NOT NULL DEFAULT 'emby-proxy-token',
                username TEXT NOT NULL DEFAULT 'admin',
                password TEXT NOT NULL DEFAULT 'admin123',
                log_level TEXT NOT NULL DEFAULT 'INFO',
                created_at INTEGER DEFAULT (unixepoch()),
                updated_at INTEGER DEFAULT (unixepoch())
            );

            -- Emby配置表
            CREATE TABLE IF NOT EXISTS emby_config (
                id INTEGER PRIMARY KEY DEFAULT 1,
                enable INTEGER NOT NULL DEFAULT 0,
                server TEXT NOT NULL DEFAULT '',
                api_key TEXT NOT NULL DEFAULT '',
                port INTEGER NOT NULL DEFAULT 8096,
                host TEXT NOT NULL DEFAULT '0.0.0.0',
                proxy_enable INTEGER DEFAULT 1,
                redirect_enable INTEGER DEFAULT 1,
                ssl_verify INTEGER DEFAULT 0,
                cache_enable INTEGER DEFAULT 1,
                cache_expire_time INTEGER DEFAULT 3600,
                modify_playback_info INTEGER DEFAULT 0,
                modify_items_info INTEGER DEFAULT 1,
                path_mapping_enable INTEGER DEFAULT 0,
                path_mapping_from TEXT DEFAULT '',
                path_mapping_to TEXT DEFAULT '',
                created_at INTEGER DEFAULT (unixepoch()),
                updated_at INTEGER DEFAULT (unixepoch())
            );

            -- 123网盘配置表
            CREATE TABLE IF NOT EXISTS pan123_config (
                id INTEGER PRIMARY KEY DEFAULT 1,
                enable INTEGER NOT NULL DEFAULT 0,
                token TEXT DEFAULT '',
                passport TEXT DEFAULT '',
                password TEXT DEFAULT '',
                client_id TEXT DEFAULT '',
                client_secret TEXT DEFAULT '',
                mount_path TEXT NOT NULL DEFAULT '/123',
                use_open_api INTEGER DEFAULT 1,
                open_api_token TEXT DEFAULT '',
                fallback_to_search INTEGER DEFAULT 1,
                download_mode TEXT DEFAULT 'direct',
                url_auth_enable INTEGER DEFAULT 0,
                url_auth_secret_key TEXT DEFAULT '',
                url_auth_uid TEXT DEFAULT '',
                url_auth_expire_time INTEGER DEFAULT 3600,
                custom_domains TEXT DEFAULT '',
                created_at INTEGER DEFAULT (unixepoch()),
                updated_at INTEGER DEFAULT (unixepoch())
            );
            """
            
            with self.db.get_cursor() as cursor:
                cursor.executescript(schema_sql)
            
            logger.info("配置表架构初始化完成")
        except Exception as e:
            logger.error(f"配置表初始化失败: {e}")

    # ==================== Service 配置 ====================

    def get_service_config(self) -> Dict[str, Any]:
        """获取服务配置"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT port, host, external_url, token, username, password, log_level
                    FROM service_config WHERE id = 1
                """)
                row = cursor.fetchone()
                
                if row:
                    return {
                        'port': row['port'],
                        'host': row['host'],
                        'external_url': row['external_url'],
                        'token': row['token'],
                        'username': row['username'],
                        'password': row['password'],
                        'log_level': row['log_level']
                    }
                else:
                    # 返回默认配置
                    return self._get_default_service_config()
        except Exception as e:
            logger.error(f"获取服务配置失败: {e}")
            return self._get_default_service_config()

    def save_service_config(self, config: Dict[str, Any]) -> bool:
        """保存服务配置"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO service_config 
                    (id, port, host, external_url, token, username, password, log_level, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, unixepoch())
                """, (
                    config.get('port', 5245),
                    config.get('host', '0.0.0.0'),
                    config.get('external_url', ''),
                    config.get('token', 'emby-proxy-token'),
                    config.get('username', 'admin'),
                    config.get('password', 'admin123'),
                    config.get('log_level', 'INFO')
                ))
                return True
        except Exception as e:
            logger.error(f"保存服务配置失败: {e}")
            return False

    def _get_default_service_config(self) -> Dict[str, Any]:
        """获取默认服务配置"""
        return {
            'port': 5245,
            'host': '0.0.0.0',
            'external_url': '',
            'token': 'emby-proxy-token',
            'username': 'admin',
            'password': 'admin123',
            'log_level': 'INFO'
        }

    # ==================== Emby 配置 ====================

    def get_emby_config(self) -> Dict[str, Any]:
        """获取Emby配置"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT enable, server, api_key, port, host, proxy_enable, redirect_enable,
                           ssl_verify, cache_enable, cache_expire_time, modify_playback_info,
                           modify_items_info, path_mapping_enable, path_mapping_from, path_mapping_to
                    FROM emby_config WHERE id = 1
                """)
                row = cursor.fetchone()
                
                if row:
                    emby_config = {
                        'enable': bool(row['enable']),
                        'server': row['server'],
                        'api_key': row['api_key'],
                        'port': row['port'],
                        'host': row['host'],
                        'proxy_enable': bool(row['proxy_enable']),
                        'redirect_enable': bool(row['redirect_enable']),
                        'ssl_verify': bool(row['ssl_verify']),
                        'cache_enable': bool(row['cache_enable']),
                        'cache_expire_time': row['cache_expire_time'],
                        'modify_playback_info': bool(row['modify_playback_info']),
                        'modify_items_info': bool(row['modify_items_info']),
                        'path_mapping': {
                            'enable': bool(row['path_mapping_enable']),
                            'from': row['path_mapping_from'],
                            'to': row['path_mapping_to']
                        }
                    }
                    
                    # 🛡️ 加载客户端拦截配置
                    client_filter = self._get_client_filter_config()
                    if client_filter:
                        emby_config['client_filter'] = client_filter
                    
                    return emby_config
                else:
                    return self._get_default_emby_config()
        except Exception as e:
            logger.error(f"获取Emby配置失败: {e}")
            return self._get_default_emby_config()

    def save_emby_config(self, config: Dict[str, Any]) -> bool:
        """保存Emby配置"""
        try:
            path_mapping = config.get('path_mapping', {})
            client_filter = config.get('client_filter', {})
            
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO emby_config 
                    (id, enable, server, api_key, port, host, proxy_enable, redirect_enable,
                     ssl_verify, cache_enable, cache_expire_time, modify_playback_info,
                     modify_items_info, path_mapping_enable, path_mapping_from, path_mapping_to, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, unixepoch())
                """, (
                    1 if config.get('enable', False) else 0,
                    config.get('server', ''),
                    config.get('api_key', ''),
                    config.get('port', 8096),
                    config.get('host', '0.0.0.0'),
                    1 if config.get('proxy_enable', True) else 0,
                    1 if config.get('redirect_enable', True) else 0,
                    1 if config.get('ssl_verify', False) else 0,
                    1 if config.get('cache_enable', True) else 0,
                    config.get('cache_expire_time', 3600),
                    1 if config.get('modify_playback_info', False) else 0,
                    1 if config.get('modify_items_info', True) else 0,
                    1 if path_mapping.get('enable', False) else 0,
                    path_mapping.get('from', ''),
                    path_mapping.get('to', '')
                ))
                
                # 🛡️ 保存客户端拦截配置到单独的表
                if client_filter:
                    self._save_client_filter_config(client_filter)
                
                logger.info(f"Emby配置已保存: server={config.get('server', '')}")
                return True
        except Exception as e:
            logger.error(f"保存Emby配置失败: {e}")
            return False

    def _save_client_filter_config(self, client_filter: Dict[str, Any]) -> bool:
        """保存客户端拦截配置"""
        try:
            import json
            
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO client_filter_config 
                    (id, enable, mode, blocked_clients, blocked_devices, blocked_ips,
                     allowed_clients, allowed_devices, allowed_ips, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, unixepoch())
                """, (
                    1 if client_filter.get('enable', False) else 0,
                    client_filter.get('mode', 'blacklist'),
                    json.dumps(client_filter.get('blocked_clients', [])),
                    json.dumps(client_filter.get('blocked_devices', [])),
                    json.dumps(client_filter.get('blocked_ips', [])),
                    json.dumps(client_filter.get('allowed_clients', [])),
                    json.dumps(client_filter.get('allowed_devices', [])),
                    json.dumps(client_filter.get('allowed_ips', []))
                ))
                
                logger.info(f"🛡️ 客户端拦截配置已保存: enable={client_filter.get('enable')}")
                return True
        except Exception as e:
            logger.error(f"保存客户端拦截配置失败: {e}")
            return False

    def _get_client_filter_config(self) -> Dict[str, Any]:
        """获取客户端拦截配置"""
        try:
            import json
            
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT enable, mode, blocked_clients, blocked_devices, blocked_ips,
                           allowed_clients, allowed_devices, allowed_ips
                    FROM client_filter_config WHERE id = 1
                """)
                row = cursor.fetchone()
                
                if row:
                    return {
                        'enable': bool(row['enable']),
                        'mode': row['mode'],
                        'blocked_clients': json.loads(row['blocked_clients'] or '[]'),
                        'blocked_devices': json.loads(row['blocked_devices'] or '[]'),
                        'blocked_ips': json.loads(row['blocked_ips'] or '[]'),
                        'allowed_clients': json.loads(row['allowed_clients'] or '[]'),
                        'allowed_devices': json.loads(row['allowed_devices'] or '[]'),
                        'allowed_ips': json.loads(row['allowed_ips'] or '[]')
                    }
                else:
                    return {
                        'enable': False,
                        'mode': 'blacklist',
                        'blocked_clients': [],
                        'blocked_devices': [],
                        'blocked_ips': [],
                        'allowed_clients': [],
                        'allowed_devices': [],
                        'allowed_ips': []
                    }
        except Exception as e:
            logger.error(f"获取客户端拦截配置失败: {e}")
            return {
                'enable': False,
                'mode': 'blacklist',
                'blocked_clients': [],
                'blocked_devices': [],
                'blocked_ips': [],
                'allowed_clients': [],
                'allowed_devices': [],
                'allowed_ips': []
            }

    def _get_default_emby_config(self) -> Dict[str, Any]:
        """获取默认Emby配置"""
        return {
            'enable': False,
            'server': '',
            'api_key': '',
            'port': 8096,
            'host': '0.0.0.0',
            'proxy_enable': True,
            'redirect_enable': True,
            'ssl_verify': False,
            'cache_enable': True,
            'cache_expire_time': 3600,
            'modify_playback_info': False,
            'modify_items_info': True,
            'path_mapping': {
                'enable': False,
                'from': '',
                'to': ''
            }
        }

    # ==================== 123网盘 配置 ====================

    def get_pan123_config(self) -> Dict[str, Any]:
        """获取123网盘配置"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT enable, token, passport, password, client_id, client_secret, mount_path,
                           use_open_api, open_api_token, fallback_to_search, download_mode,
                           url_auth_enable, url_auth_secret_key, url_auth_uid, url_auth_expire_time,
                           custom_domains
                    FROM pan123_config WHERE id = 1
                """)
                row = cursor.fetchone()
                
                if row:
                    # 处理自定义域名（从JSON字符串转换为数组）
                    custom_domains = []
                    try:
                        if row['custom_domains']:
                            custom_domains = json.loads(row['custom_domains'])
                    except:
                        custom_domains = []
                    
                    return {
                        'enable': bool(row['enable']),
                        'token': row['token'],
                        'passport': row['passport'],
                        'password': row['password'],
                        'client_id': row['client_id'],
                        'client_secret': row['client_secret'],
                        'mount_path': row['mount_path'],
                        'use_open_api': bool(row['use_open_api']),
                        'open_api_token': row['open_api_token'],
                        'fallback_to_search': bool(row['fallback_to_search']),
                        'download_mode': row['download_mode'],
                        'url_auth': {
                            'enable': bool(row['url_auth_enable']),
                            'secret_key': row['url_auth_secret_key'],
                            'uid': row['url_auth_uid'],
                            'expire_time': row['url_auth_expire_time'],
                            'custom_domains': custom_domains
                        }
                    }
                else:
                    return self._get_default_pan123_config()
        except Exception as e:
            logger.error(f"获取123网盘配置失败: {e}")
            return self._get_default_pan123_config()

    def save_pan123_config(self, config: Dict[str, Any]) -> bool:
        """保存123网盘配置"""
        try:
            url_auth = config.get('url_auth', {})
            
            # 处理自定义域名（转换为JSON字符串）
            custom_domains_json = json.dumps(url_auth.get('custom_domains', []))
            
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO pan123_config 
                    (id, enable, token, passport, password, client_id, client_secret, mount_path,
                     use_open_api, open_api_token, fallback_to_search, download_mode,
                     url_auth_enable, url_auth_secret_key, url_auth_uid, url_auth_expire_time,
                     custom_domains, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, unixepoch())
                """, (
                    1 if config.get('enable', False) else 0,
                    config.get('token', ''),
                    config.get('passport', ''),
                    config.get('password', ''),
                    config.get('client_id', ''),
                    config.get('client_secret', ''),
                    config.get('mount_path', '/123'),
                    1 if config.get('use_open_api', True) else 0,
                    config.get('open_api_token', ''),
                    1 if config.get('fallback_to_search', True) else 0,
                    config.get('download_mode', 'direct'),
                    1 if url_auth.get('enable', False) else 0,
                    url_auth.get('secret_key', ''),
                    url_auth.get('uid', ''),
                    url_auth.get('expire_time', 3600),
                    custom_domains_json
                ))
                
                logger.info(f"123网盘配置已保存: client_id={config.get('client_id', '')[:8]}...")
                return True
        except Exception as e:
            logger.error(f"保存123网盘配置失败: {e}")
            return False

    def _get_default_pan123_config(self) -> Dict[str, Any]:
        """获取默认123网盘配置"""
        return {
            'enable': False,
            'token': '',
            'passport': '',
            'password': '',
            'client_id': '',
            'client_secret': '',
            'mount_path': '/123',
            'use_open_api': True,
            'open_api_token': '',
            'fallback_to_search': True,
            'download_mode': 'direct',
            'url_auth': {
                'enable': False,
                'secret_key': '',
                'uid': '',
                'expire_time': 3600,
                'custom_domains': []
            }
        }

    # ==================== 统一配置接口 ====================

    def load_config(self) -> Dict[str, Any]:
        """加载完整配置"""
        try:
            config = {
                'service': self.get_service_config(),
                'emby': self.get_emby_config(),
                '123': self.get_pan123_config()
            }
            
            logger.debug("配置加载完成")
            return config
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            # 返回默认配置
            return {
                'service': self._get_default_service_config(),
                'emby': self._get_default_emby_config(),
                '123': self._get_default_pan123_config()
            }

    def save_config(self, config: Dict[str, Any]) -> bool:
        """保存完整配置"""
        try:
            success = True
            
            # 分别保存各个配置段
            if 'service' in config:
                if not self.save_service_config(config['service']):
                    success = False
                    logger.error("保存服务配置失败")
            
            if 'emby' in config:
                if not self.save_emby_config(config['emby']):
                    success = False
                    logger.error("保存Emby配置失败")
            
            if '123' in config:
                if not self.save_pan123_config(config['123']):
                    success = False
                    logger.error("保存123网盘配置失败")
            
            if success:
                logger.info("所有配置保存成功")
            
            return success
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False

    def get_safe_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """获取安全配置（隐藏敏感信息）"""
        import copy
        safe_config = copy.deepcopy(config)
        
        # 隐藏敏感信息
        if 'service' in safe_config and safe_config['service'].get('password'):
            safe_config['service']['password'] = '******'
            safe_config['service']['password_configured'] = True
        
        if 'emby' in safe_config and safe_config['emby'].get('api_key'):
            safe_config['emby']['api_key'] = '******'
            safe_config['emby']['api_key_configured'] = True
        
        if '123' in safe_config:
            if safe_config['123'].get('token'):
                safe_config['123']['token'] = '******'
                safe_config['123']['token_configured'] = True
            
            if safe_config['123'].get('password'):
                safe_config['123']['password'] = '******'
                safe_config['123']['password_configured'] = True
            
            if safe_config['123'].get('client_secret'):
                safe_config['123']['client_secret'] = '******'
                safe_config['123']['client_secret_configured'] = True
            
            if safe_config['123'].get('url_auth', {}).get('secret_key'):
                safe_config['123']['url_auth']['secret_key'] = '******'
                safe_config['123']['url_auth']['secret_key_configured'] = True
        
        return safe_config

    # ==================== 配置初始化 ====================
    
    def initialize_default_config(self) -> bool:
        """初始化默认配置（仅在第一次启动时）"""
        try:
            # 检查是否已有配置
            service_config = self.get_service_config()
            if service_config.get('port') != 5245:  # 有自定义配置
                return True  # 已有配置，无需初始化
            
            print("首次启动，初始化默认配置...")
            
            # 初始化默认服务配置
            default_service = self._get_default_service_config()
            self.save_service_config(default_service)
            
            # 初始化默认Emby配置
            default_emby = self._get_default_emby_config()
            self.save_emby_config(default_emby)
            
            # 初始化默认123网盘配置
            default_pan123 = self._get_default_pan123_config()
            self.save_pan123_config(default_pan123)
            
            print("✅ 默认配置初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"配置初始化失败: {e}")
            return False

    def clear_all_config(self) -> bool:
        """清除所有配置（恢复默认值）"""
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("DELETE FROM service_config WHERE id = 1")
                cursor.execute("DELETE FROM emby_config WHERE id = 1") 
                cursor.execute("DELETE FROM pan123_config WHERE id = 1")
            
            logger.info("所有配置已清除")
            return True
        except Exception as e:
            logger.error(f"清除配置失败: {e}")
            return False
