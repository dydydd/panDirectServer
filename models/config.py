#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

class ConfigManager:
    """配置管理器"""

    def __init__(self):
        self.CONFIG_FILE = Path('config/config.json')
        self.CONFIG_TEMPLATE_FILE = Path('config/config.json.template')
        self.DEFAULT_CONFIG = {
            'service': {
                'port': 5245,
                'host': '0.0.0.0',
                'external_url': '',  # 外部访问地址，用于代理模式，如: http://your-server.com:5245
                'token': 'emby-proxy-token',
                'username': 'admin',
                'password': 'admin123',
                'log_level': 'INFO'  # DEBUG, INFO, WARNING, ERROR
            },
            'emby': {
                'enable': False,
                'server': 'http://localhost:8096',
                'api_key': '',
                'port': 8096,
                'host': '0.0.0.0',
                'proxy_enable': True,
                'redirect_enable': True,
                'ssl_verify': False,
                'cache_enable': True,
                'cache_expire_time': 3600,
                'modify_playback_info': False,  # 禁用以提高速度
                'modify_items_info': True,
                'path_mapping': {
                    'enable': False,
                    'from': '',
                    'to': ''
                }
            },
            '123': {
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
                'url_auth': {
                    'enable': False,
                    'secret_key': '',
                    'uid': '',
                    'expire_time': 3600,
                    'custom_domains': []
                }
            }
        }

    def load_config(self):
        """加载配置文件"""
        # 如果存在模板文件且不存在配置文件，从模板生成配置文件
        if self.CONFIG_TEMPLATE_FILE.exists() and not self.CONFIG_FILE.exists():
            self._generate_config_from_template()
        
        if self.CONFIG_FILE.exists():
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置
                for key in self.DEFAULT_CONFIG:
                    if key not in config:
                        config[key] = self.DEFAULT_CONFIG[key]
                    elif isinstance(self.DEFAULT_CONFIG[key], dict):
                        for subkey in self.DEFAULT_CONFIG[key]:
                            if subkey not in config[key]:
                                config[key][subkey] = self.DEFAULT_CONFIG[key][subkey]
                return config
        return self.DEFAULT_CONFIG.copy()

    def _generate_config_from_template(self):
        """从模板文件生成配置文件"""
        if not self.CONFIG_TEMPLATE_FILE.exists():
            return
        
        with open(self.CONFIG_TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # 直接复制模板内容到配置文件
        self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write(template_content)

    def save_config(self, config):
        """保存配置文件"""
        self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def get_safe_config(self, config):
        """获取安全的配置（隐藏敏感信息）"""
        safe_config = config.copy()
        if safe_config.get('service', {}).get('password'):
            safe_config['service']['password'] = '******'
        if safe_config.get('emby', {}).get('api_key'):
            safe_config['emby']['api_key'] = '******' if safe_config['emby']['api_key'] else ''
        if safe_config.get('123', {}).get('token'):
            safe_config['123']['token'] = '******' if safe_config['123']['token'] else ''
        if safe_config.get('123', {}).get('password'):
            safe_config['123']['password'] = '******' if safe_config['123']['password'] else ''
        if safe_config.get('123', {}).get('client_secret'):
            safe_config['123']['client_secret'] = '******' if safe_config['123']['client_secret'] else ''
        if safe_config.get('123', {}).get('open_api_token'):
            safe_config['123']['open_api_token'] = '******' if safe_config['123']['open_api_token'] else ''
        if safe_config.get('123', {}).get('url_auth', {}).get('secret_key'):
            safe_config['123']['url_auth']['secret_key'] = '******' if safe_config['123']['url_auth']['secret_key'] else ''
        return safe_config