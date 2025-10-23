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
                
                # 第三步：测试直链是否有效（可选，可能增加延迟）
                # 注释掉测试环节以提高速度，由上层缓存机制处理
                # try:
                #     import requests
                #     test_response = requests.head(direct_url, timeout=5, allow_redirects=True)
                #     if test_response.status_code != 200:
                #         logger.warning(f"⚠️ 直链无效: {test_response.status_code}，降级到代理下载")
                #         return self._get_proxied_download_link(file_name, mapped_path)
                # except Exception as e:
                #     logger.warning(f"⚠️ 直链测试失败: {e}，降级到代理下载")
                #     return self._get_proxied_download_link(file_name, mapped_path)

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

            # 写入缓存（可选）
            if use_cache and mapped_path:
                cache_key = f"123_proxy:{mapped_path}"
                try:
                    self.cache.set_direct_link(cache_key, proxied_url, expire_time=300)
                except Exception:
                    pass

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
            
            # 获取服务器配置
            service_config = self.config.get('service', {})
            port = service_config.get('port', 5245)
            
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
                        # 替换为服务端口
                        if ':' in host:
                            host = host.split(':')[0]
                        proxied_url = f"{scheme}://{host}:{port}/proxy/download?url={encoded_url}"
                        logger.info(f"🔄 自动检测地址生成代理URL: {proxied_url[:80]}...")
                    else:
                        # 回退：使用localhost
                        proxied_url = f"http://localhost:{port}/proxy/download?url={encoded_url}"
                        logger.warning(f"⚠️ 未配置external_url且无法自动检测，使用localhost: {proxied_url[:80]}...")
                except Exception as e:
                    # 回退：使用localhost
                    proxied_url = f"http://localhost:{port}/proxy/download?url={encoded_url}"
                    logger.warning(f"⚠️ 地址检测失败，使用localhost: {e}")
            
            return proxied_url

        except Exception as e:
            logger.error(f"❌ 代理下载链接生成异常: {e}")
            return download_url

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

