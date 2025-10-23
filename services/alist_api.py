#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import json
from flask import request, jsonify
from models.config import ConfigManager
from utils.cache import CacheManager

logger = logging.getLogger(__name__)

class AlistApiService:
    """Alist API 兼容服务"""

    def __init__(self, cache_manager=None):
        self.config_manager = ConfigManager()
        self.cache_manager = cache_manager or CacheManager()

    def handle_fs_get(self):
        """处理 /api/fs/get 请求"""
        try:
            data = request.get_json()

            # 模拟 Alist 的文件信息响应
            response = {
                "code": 200,
                "message": "success",
                "data": {
                    "name": data.get('path', '').split('/')[-1],
                    "size": 0,
                    "is_dir": False,
                    "modified": "2023-01-01T00:00:00Z",
                    "created": "2023-01-01T00:00:00Z",
                    "sign": "",
                    "thumb": "",
                    "type": 1  # 文件类型
                }
            }

            return jsonify(response)

        except Exception as e:
            logger.error(f"❌ 处理 fs/get 请求异常: {e}")
            return jsonify({
                "code": 500,
                "message": str(e),
                "data": None
            }), 500

    def handle_fs_list(self):
        """处理 /api/fs/list 请求"""
        try:
            data = request.get_json()

            # 模拟 Alist 的目录列表响应
            response = {
                "code": 200,
                "message": "success",
                "data": {
                    "content": [],
                    "total": 0,
                    "readme": "",
                    "write": False,
                    "provider": "Mock"
                }
            }

            return jsonify(response)

        except Exception as e:
            logger.error(f"❌ 处理 fs/list 请求异常: {e}")
            return jsonify({
                "code": 500,
                "message": str(e),
                "data": None
            }), 500

    def handle_fs_link(self):
        """处理 /api/fs/link 请求 - 获取文件直链"""
        try:
            data = request.get_json()
            file_path = data.get('path', '')

            logger.debug(f"请求获取文件直链: {file_path}")

            # 应用路径映射
            config = self.config_manager.load_config()
            mapped_url = self.apply_path_mapping(file_path, config)

            if mapped_url:
                logger.debug(f"路径映射成功: {file_path} -> {mapped_url}")

                response = {
                    "code": 200,
                    "message": "success",
                    "data": {
                        "raw_url": mapped_url,
                        "url": mapped_url,
                        "header": {},
                        "expire": ""
                    }
                }
            else:
                logger.debug(f"路径映射失败: {file_path}")
                response = {
                    "code": 404,
                    "message": "文件路径映射失败",
                    "data": None
                }

            return jsonify(response)

        except Exception as e:
            logger.error(f"❌ 处理 fs/link 请求异常: {e}")
            return jsonify({
                "code": 500,
                "message": str(e),
                "data": None
            }), 500

    def handle_auth_login(self):
        """处理 /api/auth/login 请求"""
        try:
            data = request.get_json()
            username = data.get('username', '')
            password = data.get('password', '')

            config = self.config_manager.load_config()

            # 验证管理员账号
            if (username == config['service']['username'] and
                password == config['service']['password']):

                response = {
                    "code": 200,
                    "message": "success",
                    "data": {
                        "token": config['service']['token']
                    }
                }
            else:
                response = {
                    "code": 401,
                    "message": "用户名或密码错误",
                    "data": None
                }

            return jsonify(response)

        except Exception as e:
            logger.error(f"❌ 处理 auth/login 请求异常: {e}")
            return jsonify({
                "code": 500,
                "message": str(e),
                "data": None
            }), 500

    def apply_path_mapping(self, file_path, config):
        """应用路径映射，将虚拟路径转换为真实URL"""
        try:
            if not config['emby']['path_mapping']['enable']:
                logger.info(f"路径映射未启用，所有资源走本地代理")
                return 'LOCAL_PROXY'

            from_prefix = config['emby']['path_mapping']['from']
            to_prefix = config['emby']['path_mapping']['to']

            # 检查缓存
            cache_key = f"link:{file_path}"
            if self.cache_manager.is_direct_link_valid(cache_key):
                cached = self.cache_manager.get_direct_link(cache_key)
                logger.debug(f"缓存命中: {file_path}")
                return cached['url']

            # 执行路径映射
            if not file_path.startswith(from_prefix):
                logger.info(f"路径不匹配网盘前缀，走本地代理: {file_path[:50]}... (前缀: {from_prefix})")
                return 'LOCAL_PROXY'

            # 替换路径前缀 - 这是网盘资源
            mapped_path = file_path.replace(from_prefix, to_prefix, 1)
            logger.debug(f"网盘路径映射: {file_path} -> {mapped_path}")

            # 缓存结果
            expire_time = config['emby'].get('cache_expire_time', 3600)
            self.cache_manager.set_direct_link(cache_key, mapped_path, expire_time)
            logger.debug(f"已缓存直链，过期: {expire_time}s")

            return mapped_path

        except Exception as e:
            logger.error(f"❌ 路径映射异常: {e}")
            return 'LOCAL_PROXY'  # 异常时也走本地代理