#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
123网盘服务（精简版）
仅通过“自定义域名 + 映射路径直出 + URL鉴权”获取直链
"""

import os
import re
import time
import logging
import hashlib
import requests

# 配置日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 如果没有处理器，添加控制台处理器
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

from utils.url_auth import URLAuthManager
from utils.cache import CacheManager


class Pan123Service:
    """123网盘服务"""
    
    def __init__(self, client, config):
        self.client = client
        self.config = config
        self.auth_manager = URLAuthManager()
        self.cache = CacheManager()
    
    def get_file_direct_link(self, file_name, mapped_path=None):
        """
        获取文件直链（支持直链模式和代理模式切换）
        
        流程：
        1. 检查下载模式设置
        2. 直链模式：尝试自定义域名直出 + URL鉴权
        3. 代理模式：通过API获取下载链接 + 代理处理
        
        :param file_name: 文件名
        :param mapped_path: 映射后的路径
        :return: 文件信息（包含raw_url）
        """
        
        # 必须提供映射后的网盘路径
        if not mapped_path:
            return None

        # 检查下载模式设置
        download_mode = self.config.get('123', {}).get('download_mode', 'direct')

        # 第0步：命中直链短期缓存（按映射路径缓存，避免同名冲突）
        # 注意：直链模式（域名+路径）不缓存，代理模式才缓存（避免频繁API查询）
        # 添加版本标识，确保签名逻辑更新后不使用旧缓存
        cache_key = f"123:{mapped_path}:{download_mode}:v2"
        
        # 只有代理模式才使用缓存
        if download_mode == 'proxy' and self.cache.is_direct_link_valid(cache_key):
            cached = self.cache.get_direct_link(cache_key) or {}
            url = cached.get('url')
            if url:
                logger.info(f"⚡ 代理直链缓存命中: {file_name}")
                return {
                    'name': file_name,
                    'size': 0,
                    'is_dir': False,
                    'modified': '',
                    'raw_url': url,
                    'sign': '',
                    'header': {}
                }

        # 根据下载模式选择处理方式
        if download_mode == 'proxy':
            result = self._get_proxied_download_link(file_name, mapped_path)
            if result:
                # 缓存代理下载链接
                try:
                    self.cache.set_direct_link(cache_key, result['raw_url'], expire_time=300)
                except Exception:
                    pass
            return result
        
        elif download_mode == 'direct':
            try:
                # 第一步：自定义域名 + 路径直出
                if not self._can_build_from_domain_path():
                    logger.warning("⚠️ 未启用URL鉴权或未配置自定义域名，降级到代理下载")
                    return self._get_proxied_download_link(file_name, mapped_path)
                
                direct_url = self._build_url_from_domain_and_path(mapped_path)
                if not direct_url:
                    logger.warning("⚠️ 域名直出失败，降级到代理下载")
                    return self._get_proxied_download_link(file_name, mapped_path)

                # 第二步：添加URL鉴权
                direct_url = self._add_url_auth(direct_url)
                
                # 第三步：快速直链验证（优化超时时间）
                if self._quick_validate_direct_url(direct_url):
                    logger.info(f"✅ 直连验证成功: {file_name}")
                else:
                    logger.warning(f"⚠️ 直连验证失败，快速降级到代理下载")
                    return self._get_fast_proxied_download_link(file_name, mapped_path)

                # 第四步：直链模式不需要缓存（域名+路径构建很快）
                # 只在上层Emby代理中缓存最终结果，避免重复查询Emby API
                # 注释：代理模式才需要缓存，因为需要API查询
                
                logger.debug(f"🔗 直链模式成功: {file_name}")
                
                # 返回完整信息
                return {
                    'name': file_name,
                    'size': 0,
                    'is_dir': False,
                    'modified': '',
                    'raw_url': direct_url,
                    'sign': '',
                    'header': {}
                }
                
            except Exception as e:
                logger.error(f"❌ 直链模式异常: {e}，降级到代理下载")
                return self._get_proxied_download_link(file_name, mapped_path)
        
        else:
            logger.error(f"❌ 不支持的下载模式: {download_mode}")
            return None

    def _get_proxied_download_link(self, file_name, mapped_path=None, use_cache=True):
        """
        通过代理方式获取下载链接（支持缓存控制）
        
        :param file_name: 文件名
        :param mapped_path: 映射后的路径（可选）
        :param use_cache: 是否使用缓存
        :return: 文件信息（包含代理后的下载链接）
        """
        try:
            # 提取文件名中的文件ID或其他标识
            file_id_match = re.search(r'\[(\d+)\]', file_name)
            file_id = file_id_match.group(1) if file_id_match else None

            # 如果没有文件ID，尝试搜索获取
            if not file_id:
                search_result = self.client.fs_list_new({
                    'SearchData': file_name,
                    'limit': 1
                })
                
                if search_result and search_result.get('code') == 0:
                    items = search_result.get('data', {}).get('InfoList', [])
                    if items:
                        file_id = items[0].get('FileId')

            if not file_id:
                logger.error(f"❌ 无法获取文件ID: {file_name}")
                return None

            # 获取下载链接
            download_url = self.client.download_url({'FileID': file_id})
            
            if not download_url:
                logger.error(f"❌ 获取下载链接失败: {file_name}")
                return None

            # 通过代理方式处理下载链接
            proxied_url = self._proxy_download_url(download_url)

            # 不缓存代理链接，因为代理链接容易失效
            # 代理链接通过服务器转发，链接本身不会失效，但内容链接可能失效
            # 为了确保获取最新的下载链接，不缓存代理URL
            logger.debug(f"📝 代理链接不缓存，确保获取最新下载链接")

            return {
                'name': file_name,
                'size': 0,
                'is_dir': False,
                'modified': '',
                'raw_url': proxied_url,
                'sign': '',
                'header': {}
            }

        except Exception as e:
            logger.error(f"❌ 代理下载链接获取异常: {e}")
            return None

    def _proxy_download_url(self, download_url):
        """
        对下载链接进行代理处理 - 返回完整的代理URL
        
        :param download_url: 原始下载链接
        :return: 代理后的下载链接（完整URL）
        """
        try:
            from urllib.parse import quote
            
            # ⚠️ 关键：对原始下载链接进行URL编码，避免参数混淆
            encoded_url = quote(download_url, safe='')
            
            # 动态读取Emby反向代理端口配置
            emby_config = self.config.get('emby', {})
            service_config = self.config.get('service', {})
            
            # 从配置中动态获取Emby代理端口，允许用户自定义
            emby_proxy_port = emby_config.get('port', 8096)
            port = emby_proxy_port
            
            logger.debug(f"📡 动态读取Emby代理端口: {port}")
            
            # 优先使用配置的外部访问地址（用于代理模式）
            external_url = service_config.get('external_url', '')
            
            if external_url:
                # 使用配置的外部访问地址（推荐）
                # 例如: http://your-server.com:5245 或 https://your-domain.com
                base_url = external_url.rstrip('/')
                proxied_url = f"{base_url}/proxy/download?url={encoded_url}"
                logger.info(f"🔄 使用外部地址生成代理URL: {proxied_url[:80]}...")
            else:
                # 如果没有配置外部地址，使用请求头中的Host（自动检测）
                try:
                    from flask import request
                    if request:
                        # 从当前请求获取客户端访问的地址
                        scheme = 'https' if request.is_secure else 'http'
                        host = request.host  # 包含端口，如 dy.127255.best:8096
                        # 使用Emby代理端口
                        if ':' in host:
                            host = host.split(':')[0]
                        proxied_url = f"{scheme}://{host}:{port}/proxy/download?url={encoded_url}"
                        logger.info(f"🔄 使用Emby代理端口生成代理URL: {proxied_url[:80]}...")
                    else:
                        # 回退：使用localhost的Emby代理端口
                        proxied_url = f"http://localhost:{port}/proxy/download?url={encoded_url}"
                        logger.info(f"🔄 回退使用localhost Emby代理端口: {proxied_url[:80]}...")
                except Exception as e:
                    # 回退：使用localhost的Emby代理端口
                    proxied_url = f"http://localhost:{port}/proxy/download?url={encoded_url}"
                    logger.info(f"🔄 地址检测失败，使用localhost Emby代理端口: {e}")
            
            return proxied_url

        except Exception as e:
            logger.error(f"❌ 代理下载链接生成异常: {e}")
            return download_url
    
    def _quick_validate_direct_url(self, direct_url):
        """快速验证直连URL（0.8秒超时）"""
        try:
            import requests
            logger.debug(f"🧪 快速验证直连: {direct_url[:60]}...")
            
            # 使用很短的超时时间进行快速验证
            response = requests.head(direct_url, timeout=0.8, allow_redirects=False)
            
            # 200, 206, 302, 301都认为是成功
            if response.status_code in [200, 206, 301, 302]:
                logger.debug(f"✅ 直连验证通过: HTTP {response.status_code}")
                return True
            else:
                logger.debug(f"⚠️ 直连返回: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.debug(f"⚠️ 直连验证超时(0.8s)")
            return False
        except Exception as e:
            logger.debug(f"⚠️ 直连验证异常: {e}")
            return False
    
    def _get_fast_proxied_download_link(self, file_name, mapped_path=None):
        """快速获取代理下载链接（优化版本）"""
        try:
            # 优先检查文件搜索缓存
            search_cache = self._get_cached_file_search(file_name)
            
            if search_cache:
                logger.info(f"🎯 文件搜索缓存命中: {file_name}")
                file_id = search_cache['file_id']
                
                # 直接获取下载链接，跳过搜索步骤
                download_url = self.client.download_url({'FileID': file_id})
                
                if download_url:
                    proxied_url = self._proxy_download_url(download_url)
                    
                    return {
                        'name': file_name,
                        'size': search_cache.get('file_size', 0),
                        'is_dir': False,
                        'modified': search_cache.get('created_time', ''),
                        'raw_url': proxied_url,
                        'sign': '',
                        'header': {}
                    }
            
            # 如果没有缓存，执行搜索并缓存结果
            logger.info(f"🔍 执行123网盘搜索: {file_name}")
            
            search_result = self.client.fs_list_new({
                'SearchData': file_name,
                'limit': 10
            })
            
            if search_result and search_result.get('code') == 0:
                items = search_result.get('data', {}).get('InfoList', [])
                
                # 查找精确匹配并缓存
                for item in items:
                    if item.get('FileName') == file_name and item.get('Type') == 0:
                        file_id = item['FileId']
                        
                        # 缓存搜索结果（1小时）
                        self._cache_file_search(file_name, {
                            'file_id': file_id,
                            'file_size': item.get('Size', 0),
                            'created_time': item.get('CreateAt', ''),
                            'parent_id': item.get('ParentFileId', '')
                        })
                        
                        logger.info(f"📝 文件搜索结果已缓存: {file_name}")
                        
                        # 获取下载链接
                        download_url = self.client.download_url({'FileID': file_id})
                        
                        if download_url:
                            proxied_url = self._proxy_download_url(download_url)
                            
                            return {
                                'name': file_name,
                                'size': item.get('Size', 0),
                                'is_dir': False,
                                'modified': item.get('CreateAt', ''),
                                'raw_url': proxied_url,
                                'sign': '',
                                'header': {}
                            }
                        break
            
            logger.warning(f"⚠️ 快速代理获取失败: {file_name}")
            return None
            
        except Exception as e:
            logger.error(f"❌ 快速代理下载异常: {e}")
            return None
    
    def _get_cached_file_search(self, file_name):
        """获取缓存的文件搜索结果"""
        try:
            from database.database import get_db_manager
            db = get_db_manager()
            return db.get_file_search_cache(file_name)
        except Exception:
            return None
    
    def _cache_file_search(self, file_name, file_info):
        """缓存文件搜索结果"""
        try:
            from database.database import get_db_manager
            db = get_db_manager()
            
            db.set_file_search_cache(
                filename=file_name,
                file_id=file_info['file_id'],
                file_size=file_info.get('file_size'),
                parent_id=file_info.get('parent_id'),
                created_time=file_info.get('created_time'),
                expire_seconds=3600  # 1小时缓存
            )
            return True
        except Exception as e:
            logger.warning(f"⚠️ 缓存文件搜索失败: {e}")
            return False

    def _can_build_from_domain_path(self):
        """判断是否可通过自定义域名 + 路径直出"""
        try:
            auth_cfg = self.config.get('123', {}).get('url_auth', {})
            domains = auth_cfg.get('custom_domains', []) or []
            return bool(auth_cfg.get('enable')) and len(domains) > 0
        except Exception:
            return False

    def _build_url_from_domain_and_path(self, mapped_path):
        """使用自定义域名 + 网盘映射路径直接构造直链URL"""
        try:
            # mapped_path 形如: /123/dy/... 需去除挂载前缀
            mount = (self.config.get('123', {}) or {}).get('mount_path', '/123')
            path_part = mapped_path
            if mount and mapped_path.startswith(mount):
                path_part = mapped_path[len(mount):]
            if not path_part.startswith('/'):
                path_part = '/' + path_part

            auth_cfg = self.config.get('123', {}).get('url_auth', {})
            domains = auth_cfg.get('custom_domains', []) or []
            if not domains:
                return None
            domain = domains[0].strip().rstrip('/')
            if domain.startswith('http://') or domain.startswith('https://'):
                base = domain
            else:
                base = f"https://{domain}"
            return f"{base}{path_part}"
        except Exception:
            return None
    
    def _search_file(self, file_name):
        """搜索文件获取FileID"""
        try:
            logger.info(f"🔍 搜索文件: {file_name}")
            
            search_result = self.client.fs_list_new({
                'SearchData': file_name,
                'limit': 20
            })
            
            if not search_result or search_result.get('code') != 0:
                logger.warning(f"⚠️ 搜索API返回异常")
                return None, None
            
            items = search_result.get('data', {}).get('InfoList', [])
            logger.info(f"  找到 {len(items)} 个结果")
            
            # 查找完全匹配的文件
            for item in items:
                if item.get('FileName') == file_name and item.get('Type') == 0:
                    file_id = item['FileId']
                    logger.info(f"✅ 匹配文件: FileId={file_id}")
                    return file_id, item
            
            logger.warning(f"⚠️ 未找到完全匹配的文件")
            return None, None
            
        except Exception as e:
            logger.error(f"❌ 搜索异常: {e}")
            return None, None
    
    # 已移除：OpenAPI 与 download_url 获取直链的实现
    
    def _add_url_auth(self, url):
        """添加URL鉴权签名"""
        if not url:
            return url
        
        # 检查是否启用鉴权
        auth_config = self.config.get('123', {}).get('url_auth', {})
        if not auth_config.get('enable'):
            logger.info(f"  URL鉴权未启用")
            return url
        
        # 检查是否需要鉴权（支持自定义域名）
        custom_domains = auth_config.get('custom_domains', [])
        if not self.auth_manager.is_123pan_url(url, custom_domains):
            logger.info(f"  非123网盘URL，跳过鉴权")
            return url
        
        # 获取鉴权参数
        secret_key = auth_config.get('secret_key')
        uid = auth_config.get('uid')
        expire_time = auth_config.get('expire_time', 3600)
        
        if not (secret_key and uid):
            logger.warning(f"⚠️ URL鉴权已启用但缺少配置")
            return url
        
        # 添加签名
        logger.debug(f"🔐 添加URL鉴权签名...")
        auth_url = self.auth_manager.add_auth_to_url(url, secret_key, uid, expire_time)
        
        return auth_url
    
    # 已移除：获取 OpenAPI access_token 的逻辑

