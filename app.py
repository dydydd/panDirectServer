#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import io  # 新增 io 模块导入
import json
import time
import uuid
import base64
import logging
import threading
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, send_file
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# 导入自定义模块
from utils.logger import setup_logger
from models.config import ConfigManager
from models.client import ClientManager
from utils.cache import CacheManager
from services.emby_proxy import EmbyProxyService
from services.strm_parser import StrmParserService
from services.alist_api import AlistApiService

# 设置日志
logger = setup_logger()

# 主应用（Web 管理界面 + Alist API）
app = Flask(__name__, 
            template_folder='templates',
            static_folder='templates/static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
CORS(app)

# Emby 反向代理应用（独立端口）
emby_app = Flask('emby_proxy')
emby_app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
CORS(emby_app)

# 为emby_app导入必要的模块
from flask import request, jsonify, Response

# 初始化服务
config_manager = ConfigManager()
client_manager = ClientManager()
cache_manager = CacheManager()
emby_proxy_service = EmbyProxyService(client_manager)
alist_api_service = AlistApiService(cache_manager)

def token_required(f):
    """Token 认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = config_manager.load_config()
        token = request.headers.get('Authorization', '')
        
        if token != config.get('service', {}).get('token', ''):
            return jsonify({
                'code': 403,
                'message': 'Invalid token'
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function

# ==================== 认证路由 ====================

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """登录认证"""
    data = request.get_json()
    config = config_manager.load_config()
    
    username = data.get('username')
    password = data.get('password')
    
    if (username == config.get('service', {}).get('username', '') and 
        password == config.get('service', {}).get('password', '')):
        # 生成 token
        token = config.get('service', {}).get('token', '')
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'token': token
            }
        })
    
    return jsonify({
        'code': 400,
        'message': 'Invalid credentials'
    }), 400

# ==================== Web 管理界面 ====================

@app.route('/')
def index():
    """管理界面首页"""
    return render_template('index.html')

@app.route('/clients')
def client_management():
    """客户端管理页面"""
    return render_template('client_management.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置"""
    config = config_manager.load_config()
    safe_config = config_manager.get_safe_config(config)
    return jsonify({
        'code': 200,
        'data': safe_config,
        'message': 'Configuration loaded successfully'
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置"""
    new_config = request.get_json()
    old_config = config_manager.load_config()
    
    # 处理密码字段（如果是******则保留原值）
    if new_config.get('service', {}).get('password') == '******':
        new_config['service']['password'] = old_config.get('service', {}).get('password', '')
    if new_config.get('emby', {}).get('api_key') == '******':
        new_config['emby']['api_key'] = old_config.get('emby', {}).get('api_key', '')
    if new_config.get('123', {}).get('token') == '******':
        new_config['123']['token'] = old_config.get('123', {}).get('token', '')
    if new_config.get('123', {}).get('password') == '******':
        new_config['123']['password'] = old_config.get('123', {}).get('password', '')
    if new_config.get('123', {}).get('client_secret') == '******':
        new_config['123']['client_secret'] = old_config.get('123', {}).get('client_secret', '')
    if new_config.get('123', {}).get('open_api_token') == '******':
        new_config['123']['open_api_token'] = old_config.get('123', {}).get('open_api_token', '')
    if new_config.get('123', {}).get('url_auth', {}).get('secret_key') == '******':
        new_config['123']['url_auth']['secret_key'] = old_config.get('123', {}).get('url_auth', {}).get('secret_key', '')
    
    config_manager.save_config(new_config)
    client_manager.init_clients(new_config)
    
    return jsonify({
        'code': 200,
        'message': 'Configuration updated successfully'
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取服务状态"""
    client_status = client_manager.get_status()
    cache_stats = cache_manager.get_cache_stats()

    status = {
        **client_status,
        'cache': cache_stats,
        'mode': 'STRM解析模式',
        'features': {
            'strm_parsing': True,
            'emby_proxy': True,
            'media_info_extraction': True,
            'playback_info_modification': True,
            'items_info_modification': True
        }
    }
    
    return jsonify(status)

@app.route('/api/test/123', methods=['POST'])
def test_123_connection():
    """测试123网盘连接"""
    try:
        config = config_manager.load_config()
        
        # 检查是否配置了client_id和client_secret
        if not config.get('123', {}).get('client_id') or not config.get('123', {}).get('client_secret'):
            return jsonify({
                'code': 400,
                'message': '请先配置123网盘的应用ID (client_id) 和应用密钥 (client_secret)'
            }), 400
        
        # 重新初始化123客户端
        client_manager.init_clients(config)
        
        # 检查客户端是否初始化成功
        if not client_manager.clients.get('123'):
            return jsonify({
                'code': 500,
                'message': '123网盘客户端初始化失败'
            }), 500
        
        # 测试连接
        try:
            test_result = client_manager.clients['123'].fs_list_new({'SearchData': 'test', 'limit': 1})
            if test_result and test_result.get('code') == 0:
                return jsonify({
                    'code': 200,
                    'message': '123网盘连接测试成功'
                })
            else:
                return jsonify({
                    'code': 500,
                    'message': f'123网盘连接测试失败: {test_result}'
                }), 500
        except Exception as e:
            return jsonify({
                'code': 500,
                'message': f'123网盘连接测试异常: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'测试失败: {str(e)}'
        }), 500

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """清除所有缓存"""
    result = cache_manager.clear_all_cache()

    return jsonify({
        'code': 200,
        'message': f'缓存已清除',
        'data': result
    })

@app.route('/api/download-mode', methods=['GET'])
def get_download_mode():
    """获取当前下载模式"""
    config = config_manager.load_config()
    download_mode = config.get('123', {}).get('download_mode', 'direct')
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'download_mode': download_mode,
            'available_modes': ['direct', 'proxy']
        }
    })

@app.route('/api/download-mode', methods=['POST'])
def set_download_mode():
    """设置下载模式"""
    data = request.get_json()
    new_mode = data.get('download_mode')
    
    if new_mode not in ['direct', 'proxy']:
        return jsonify({
            'code': 400,
            'message': '不支持的下载模式，支持的模式：direct, proxy'
        }), 400
    
    config = config_manager.load_config()
    if '123' not in config:
        config['123'] = {}
    config['123']['download_mode'] = new_mode
    config_manager.save_config(config)
    
    # 清除相关缓存
    cache_manager.clear_all_cache()
    
    return jsonify({
        'code': 200,
        'message': f'下载模式已切换为: {new_mode}',
        'data': {
            'download_mode': new_mode
        }
    })

@app.route('/api/clients', methods=['GET'])
def api_get_clients():
    """获取当前连接的客户端列表"""
    try:
        # 先清理过期的客户端
        if hasattr(emby_proxy_service, 'cleanup_expired_clients'):
            emby_proxy_service.cleanup_expired_clients()
        
        # 从Emby代理服务中获取客户端信息
        if hasattr(emby_proxy_service, 'connected_clients'):
            clients = emby_proxy_service.connected_clients
        else:
            clients = {}
        
        return jsonify({
            'code': 200,
            'message': '获取客户端列表成功',
            'data': {
                'clients': clients,
                'count': len(clients)
            }
        })
    except Exception as e:
        logger.error(f"获取客户端列表失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e),
            'data': None
        })

@app.route('/api/clients/block', methods=['POST'])
def api_block_client():
    """拦截客户端"""
    try:
        data = request.json
        block_type = data.get('type')  # 'client', 'device', 'ip'
        block_value = data.get('value')
        
        if not block_type or not block_value:
            return jsonify({
                'code': 400,
                'message': '参数不完整',
                'data': None
            })
        
        # 加载当前配置
        config = config_manager.load_config()
        
        # 确保client_filter配置存在
        if 'client_filter' not in config['emby']:
            config['emby']['client_filter'] = {
                'enable': False,
                'mode': 'blacklist',
                'blocked_clients': [],
                'blocked_devices': [],
                'blocked_ips': [],
                'allowed_clients': [],
                'allowed_devices': [],
                'allowed_ips': []
            }
        
        # 启用客户端拦截
        config['emby']['client_filter']['enable'] = True
        config['emby']['client_filter']['mode'] = 'blacklist'
        
        # 添加到黑名单
        if block_type == 'client':
            if block_value not in config['emby']['client_filter']['blocked_clients']:
                config['emby']['client_filter']['blocked_clients'].append(block_value)
        elif block_type == 'device':
            if block_value not in config['emby']['client_filter']['blocked_devices']:
                config['emby']['client_filter']['blocked_devices'].append(block_value)
        elif block_type == 'ip':
            if block_value not in config['emby']['client_filter']['blocked_ips']:
                config['emby']['client_filter']['blocked_ips'].append(block_value)
        
        # 保存配置
        config_manager.save_config(config)
        
        logger.warning(f"🚫 已拦截{block_type}: {block_value}")
        
        return jsonify({
            'code': 200,
            'message': f'已拦截{block_type}: {block_value}',
            'data': None
        })
        
    except Exception as e:
        logger.error(f"拦截客户端失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e),
            'data': None
        })

@app.route('/api/clients/unblock', methods=['POST'])
def api_unblock_client():
    """解除拦截客户端"""
    try:
        data = request.json
        block_type = data.get('type')  # 'client', 'device', 'ip'
        block_value = data.get('value')
        
        if not block_type or not block_value:
            return jsonify({
                'code': 400,
                'message': '参数不完整',
                'data': None
            })
        
        # 加载当前配置
        config = config_manager.load_config()
        
        # 确保client_filter配置存在
        if 'client_filter' not in config['emby']:
            return jsonify({
                'code': 400,
                'message': '客户端拦截未启用',
                'data': None
            })
        
        # 从黑名单中移除
        removed = False
        if block_type == 'client':
            if block_value in config['emby']['client_filter']['blocked_clients']:
                config['emby']['client_filter']['blocked_clients'].remove(block_value)
                removed = True
        elif block_type == 'device':
            if block_value in config['emby']['client_filter']['blocked_devices']:
                config['emby']['client_filter']['blocked_devices'].remove(block_value)
                removed = True
        elif block_type == 'ip':
            if block_value in config['emby']['client_filter']['blocked_ips']:
                config['emby']['client_filter']['blocked_ips'].remove(block_value)
                removed = True
        
        if not removed:
            return jsonify({
                'code': 400,
                'message': f'{block_type} "{block_value}" 不在拦截列表中',
                'data': None
            })
        
        # 如果所有拦截列表都为空，禁用客户端拦截
        if (not config['emby']['client_filter']['blocked_clients'] and 
            not config['emby']['client_filter']['blocked_devices'] and 
            not config['emby']['client_filter']['blocked_ips']):
            config['emby']['client_filter']['enable'] = False
        
        # 保存配置
        config_manager.save_config(config)
        
        logger.info(f"✅ 已解除拦截{block_type}: {block_value}")
        
        return jsonify({
            'code': 200,
            'message': f'已解除拦截{block_type}: {block_value}',
            'data': None
        })
        
    except Exception as e:
        logger.error(f"解除拦截失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e),
            'data': None
        })

@app.route('/api/clients/blocked', methods=['GET'])
def api_get_blocked_clients():
    """获取被拦截的客户端列表"""
    try:
        config = config_manager.load_config()
        client_filter = config.get('emby', {}).get('client_filter', {})
        
        return jsonify({
            'code': 200,
            'message': '获取拦截列表成功',
            'data': {
                'enable': client_filter.get('enable', False),
                'mode': client_filter.get('mode', 'blacklist'),
                'blocked_clients': client_filter.get('blocked_clients', []),
                'blocked_devices': client_filter.get('blocked_devices', []),
                'blocked_ips': client_filter.get('blocked_ips', [])
            }
        })
    except Exception as e:
        logger.error(f"获取拦截列表失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e),
            'data': None
        })

@app.route('/api/users/history', methods=['GET'])
def api_get_user_history():
    """获取用户历史记录"""
    try:
        if hasattr(emby_proxy_service, 'user_history'):
            user_history = emby_proxy_service.user_history
        else:
            user_history = {}
        
        return jsonify({
            'code': 200,
            'message': '获取用户历史成功',
            'data': {
                'users': user_history,
                'count': len(user_history)
            }
        })
    except Exception as e:
        logger.error(f"获取用户历史失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e),
            'data': None
        })

# ==================== Alist API 兼容 ====================

@app.route('/api/fs/get', methods=['POST'])
@token_required
def api_fs_get():
    """获取文件信息"""
    return alist_api_service.handle_fs_get()

@app.route('/api/fs/list', methods=['POST'])
@token_required
def api_fs_list():
    """列出目录内容"""
    return alist_api_service.handle_fs_list()

@app.route('/api/fs/link', methods=['POST'])
@token_required
def api_fs_link():
    """获取文件直链"""
    return alist_api_service.handle_fs_link()

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    """登录认证"""
    return alist_api_service.handle_auth_login()

# ==================== 代理下载 ====================

@app.route('/proxy/download', methods=['GET'])
@emby_app.route('/proxy/download', methods=['GET'])
def proxy_download():
    """
    代理下载 - 简单粗暴版本
    """
    try:
        # 获取完整的查询字符串
        query_string = request.query_string.decode('utf-8')
        logger.info(f"🔍 原始查询字符串: {query_string}")
        
        # 从查询字符串中提取url参数
        if not query_string.startswith('url='):
            return jsonify({'error': '缺少url参数'}), 400
        
        # 提取url=后面的所有内容
        download_url = query_string[4:]  # 去掉 'url=' 前缀
        
        # URL解码处理
        from urllib.parse import unquote
        download_url = unquote(download_url)

        # 直接下载文件
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # 支持Range请求（断点续传）
        range_header = request.headers.get('Range')
        if range_header:
            headers['Range'] = range_header
        
        response = requests.get(download_url, stream=True, timeout=30, headers=headers)
        
        # 支持206 Partial Content响应
        if response.status_code not in [200, 206]:
            logger.error(f"❌ 代理下载失败: {response.status_code}")
            return jsonify({'error': f'下载失败: {response.status_code}'}), 500
        
        # 流式传输
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        from flask import Response
        
        # 构建响应头
        response_headers = {
            'Content-Type': response.headers.get('Content-Type', 'application/octet-stream'),
            'Accept-Ranges': 'bytes',
            'Cache-Control': 'no-cache'
        }
        
        # 如果是Range请求，返回206状态码和相关头部
        if response.status_code == 206:
            response_headers['Content-Range'] = response.headers.get('Content-Range', '')
            response_headers['Content-Length'] = response.headers.get('Content-Length', '')
            status_code = 206
        else:
            response_headers['Content-Length'] = response.headers.get('Content-Length', '')
            status_code = 200
        
        return Response(
            generate(),
            status=status_code,
            headers=response_headers
        )

    except Exception as e:
        logger.error(f"❌ 代理下载异常: {e}")
        return jsonify({'error': '服务器错误'}), 500

# ==================== Emby 反向代理 ====================

@emby_app.route('/<path:path>', methods=['GET', 'POST', 'DELETE', 'PUT', 'PATCH', 'HEAD', 'OPTIONS'])
@emby_app.route('/', methods=['GET', 'POST', 'DELETE', 'PUT', 'PATCH', 'HEAD', 'OPTIONS'])
def emby_proxy(path=''):
    """Emby API 反向代理（独立端口，无需 /emby 前缀）"""
    return emby_proxy_service.proxy_request(path)

# ==================== 启动函数 ====================

def run_emby_server(config):
    """运行 Emby 反向代理服务器（独立线程）"""
    if config.get('emby', {}).get('enable'):
        emby_host = config.get('emby', {}).get('host', '0.0.0.0')
        emby_port = config.get('emby', {}).get('port', 8096)
        logger.info(f"启动 Emby 反向代理服务器: http://{emby_host}:{emby_port}")
        try:
            emby_app.run(
                host=emby_host,
                port=emby_port,
                debug=False,
                threaded=True,
                use_reloader=False
            )
        except Exception as e:
            logger.error(f"Emby 反向代理服务器启动失败: {e}")
    else:
        logger.info("Emby 反向代理未启用")

if __name__ == '__main__':
    # 初始化配置和客户端
    config = config_manager.load_config()
    
    # 设置日志级别
    log_level = config.get('service', {}).get('log_level', 'INFO')
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    logger.info(f"日志级别设置为: {log_level}")
    
    config_manager.save_config(config)
    client_manager.init_clients(config)

    # 如果启用了 Emby 反向代理，在独立线程中启动
    if config.get('emby', {}).get('enable'):
        emby_thread = threading.Thread(
            target=run_emby_server,
            args=(config,),
            daemon=True,
            name='EmbyProxyServer'
        )
        emby_thread.start()
        logger.info(f"Emby 反向代理服务器线程已启动")

    # 启动主服务（Web 管理界面 + Alist API）
    main_host = config.get('service', {}).get('host', '0.0.0.0')
    main_port = config.get('service', {}).get('port', 5245)
    logger.info(f"启动主服务: http://{main_host}:{main_port}")
    app.run(
        host=main_host,
        port=main_port,
        debug=os.environ.get('DEBUG', 'false').lower() == 'true',
        threaded=True
    )