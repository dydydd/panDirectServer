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
# SQLite 数据库管理器
from database.database import init_database

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

# 服务管理器（延迟初始化）
config_manager = None
client_manager = None  
cache_manager = None
emby_proxy_service = None
alist_api_service = None

def initialize_services():
    """初始化所有服务（在数据库初始化后）"""
    global config_manager, client_manager, cache_manager, emby_proxy_service, alist_api_service
    
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
    
    # 清理配置状态标志位（这些不应该存储在实际配置中）
    def clean_config_flags(config):
        """移除配置状态标志位"""
        import copy
        clean_config = copy.deepcopy(config)
        
        # 移除service相关标志位
        if 'service' in clean_config:
            clean_config['service'].pop('password_configured', None)
        
        # 移除emby相关标志位
        if 'emby' in clean_config:
            clean_config['emby'].pop('api_key_configured', None)
        
        # 移除123网盘相关标志位
        if '123' in clean_config:
            clean_config['123'].pop('token_configured', None)
            clean_config['123'].pop('password_configured', None)
            clean_config['123'].pop('client_secret_configured', None)
            clean_config['123'].pop('open_api_token_configured', None)
            if 'url_auth' in clean_config['123']:
                clean_config['123']['url_auth'].pop('secret_key_configured', None)
        
        return clean_config
    
    # 清理标志位
    new_config = clean_config_flags(new_config)
    
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
    from database.database import get_db_manager
    db = get_db_manager()
    
    # 加载配置文件
    config = config_manager.load_config()
    
    client_status = client_manager.get_status()
    cache_stats = cache_manager.get_cache_stats()
    db_stats = db.get_performance_stats()

    # 获取Emby配置和状态
    emby_config = config.get('emby', {})
    emby_status = {
        'enabled': emby_config.get('enable', False),
        'server': emby_config.get('server', ''),
        'port': emby_config.get('port', 8096),
        'api_key_configured': bool(emby_config.get('api_key', '')),
        'proxy_enabled': emby_config.get('proxy_enable', True),
        'path_mapping_enabled': emby_config.get('path_mapping', {}).get('enable', False),
        'status': 'configured' if emby_config.get('server') and emby_config.get('api_key') else 'not_configured'
    }

    # 获取服务配置
    service_config = config.get('service', {})
    service_status = {
        'port': service_config.get('port', 5245),
        'host': service_config.get('host', '0.0.0.0'),
        'external_url': service_config.get('external_url', ''),
        'status': 'running'
    }

    status = {
        # 网盘客户端状态
        **client_status,
        
        # Emby状态
        'emby': emby_status,
        
        # 服务状态
        'service': service_status,
        
        # 缓存状态
        'cache': cache_stats,
        
        # 数据库状态
        'database': {
            'type': 'SQLite',
            'size': db_stats.get('database_size', 0),
            'performance': '🚀 高性能优化已启用'
        },
        
        # 运行模式
        'mode': 'STRM解析模式 + SQLite 高速缓存',
        
        # 功能特性
        'features': {
            'sqlite_optimization': True,  # 新增SQLite优化特性
            'high_performance_cache': True,  # 高性能缓存
            'persistent_storage': True,  # 持久化存储
            'strm_parsing': True,
            'emby_proxy': emby_status['enabled'],
            'media_info_extraction': True,
            'playback_info_modification': emby_config.get('modify_playback_info', False),
            'items_info_modification': emby_config.get('modify_items_info', True)
        }
    }
    
    return jsonify(status)

@app.route('/api/test/emby', methods=['POST'])
def test_emby_connection():
    """测试Emby服务器连接"""
    try:
        config = config_manager.load_config()
        emby_config = config.get('emby', {})
        
        if not emby_config.get('enable'):
            return jsonify({
                'code': 400,
                'message': 'Emby服务未启用'
            }), 400
        
        server = emby_config.get('server')
        api_key = emby_config.get('api_key')
        
        if not server:
            return jsonify({
                'code': 400,
                'message': '请先配置Emby服务器地址'
            }), 400
        
        if not api_key:
            return jsonify({
                'code': 400,
                'message': '请先配置Emby API密钥'
            }), 400
        
        # 测试连接
        import requests
        test_url = f"{server}/emby/System/Info?api_key={api_key}"
        
        try:
            response = requests.get(test_url, timeout=10, verify=emby_config.get('ssl_verify', False))
            if response.status_code == 200:
                info = response.json()
                return jsonify({
                    'code': 200,
                    'message': 'Emby服务器连接测试成功',
                    'data': {
                        'server_name': info.get('ServerName', '未知'),
                        'version': info.get('Version', '未知'),
                        'operating_system': info.get('OperatingSystem', '未知')
                    }
                })
            elif response.status_code == 401:
                return jsonify({
                    'code': 401,
                    'message': 'Emby API密钥无效，请检查配置'
                }), 401
            else:
                return jsonify({
                    'code': 500,
                    'message': f'Emby服务器响应错误: HTTP {response.status_code}'
                }), 500
                
        except requests.exceptions.ConnectTimeout:
            return jsonify({
                'code': 500,
                'message': '连接Emby服务器超时，请检查服务器地址和网络'
            }), 500
        except requests.exceptions.ConnectionError:
            return jsonify({
                'code': 500,
                'message': '无法连接到Emby服务器，请检查服务器地址和状态'
            }), 500
        except Exception as e:
            return jsonify({
                'code': 500,
                'message': f'连接测试异常: {str(e)}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'测试失败: {str(e)}'
        }), 500

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
        'message': f'SQLite 缓存已清除',
        'data': result
    })

@app.route('/api/performance', methods=['GET'])
def get_performance_stats():
    """获取性能统计"""
    from database.database import get_db_manager
    db = get_db_manager()
    
    stats = db.get_performance_stats()
    
    return jsonify({
        'code': 200,
        'message': '性能统计获取成功',
        'data': {
            'optimization': '🚀 SQLite 高性能优化已启用',
            'database_size': stats.get('database_size', 0),
            'cache_stats': stats.get('cache_stats', {}),
            'api_performance': stats.get('api_stats', [])[:10],  # 最近10个API调用
            'benefits': {
                'speed_improvement': '查询速度提升 10-100x',
                'memory_efficiency': '内存使用优化 50%+',
                'data_persistence': '数据持久化，重启不丢失',
                'concurrent_support': '支持高并发访问'
            }
        }
    })

@app.route('/api/database/optimize', methods=['POST'])
def optimize_database():
    """优化数据库"""
    from database.database import get_db_manager
    db = get_db_manager()
    
    success = db.vacuum_database()
    
    if success:
        return jsonify({
            'code': 200,
            'message': '数据库优化完成',
            'data': {
                'status': 'optimized',
                'description': '已回收空间并重建索引'
            }
        })
    else:
        return jsonify({
            'code': 500,
            'message': '数据库优化失败'
        }), 500

@app.route('/api/restart', methods=['POST'])
def restart_service():
    """重启服务"""
    try:
        import threading
        import time
        
        def delayed_restart():
            """延迟重启，给客户端时间接收响应"""
            time.sleep(2)  # 等待2秒让响应返回
            logger.info("🔄 执行服务重启...")
            
            import os
            import sys
            
            try:
                # 方法1：尝试使用os._exit()强制退出
                logger.info("🛑 正在停止服务...")
                os._exit(0)
            except Exception as e:
                logger.error(f"重启失败: {e}")
                # 方法2：尝试sys.exit()
                sys.exit(0)
        
        # 在后台线程中执行重启
        restart_thread = threading.Thread(target=delayed_restart, daemon=True)
        restart_thread.start()
        
        logger.info("🔄 重启请求已接收，服务将在2秒后重启")
        
        return jsonify({
            'code': 200,
            'message': '服务重启中...',
            'data': {
                'restart_delay': 2,
                'status': 'restarting'
            }
        })
        
    except Exception as e:
        logger.error(f"重启服务失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'重启失败: {str(e)}',
            'data': None
        }), 500

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
        from database.database import get_db_manager
        db = get_db_manager()
        
        # 从SQLite数据库获取用户历史，格式化为前端期望的结构
        user_history_raw = db.get_user_history(100)  # 最近100条记录
        
        # 转换为前端期望的格式
        formatted_users = {}
        
        for record in user_history_raw:
            user_id = record['user_id']
            if user_id not in formatted_users:
                formatted_users[user_id] = {
                    'devices': [],
                    'ips': [], 
                    'last_seen': record['last_seen'],
                    'username': user_id
                }
            
            # 更新最后活动时间
            if record['last_seen'] > formatted_users[user_id]['last_seen']:
                formatted_users[user_id]['last_seen'] = record['last_seen']
            
            # 添加设备信息
            if record.get('device_name') and record.get('client_name'):
                device_info = {
                    'client': record['client_name'],
                    'device': record['device_name'],
                    'device_id': record.get('device_id', ''),
                    'version': '1.0',  # 默认版本
                    'last_seen': record['last_seen']
                }
                
                # 避免重复设备
                device_exists = False
                for existing_device in formatted_users[user_id]['devices']:
                    if existing_device.get('device_id') == device_info['device_id']:
                        existing_device['last_seen'] = max(existing_device['last_seen'], device_info['last_seen'])
                        device_exists = True
                        break
                
                if not device_exists:
                    formatted_users[user_id]['devices'].append(device_info)
            
            # 添加IP信息
            if record.get('ip_address'):
                ip_info = {
                    'ip': record['ip_address'],
                    'last_seen': record['last_seen']
                }
                
                # 避免重复IP
                ip_exists = False
                for existing_ip in formatted_users[user_id]['ips']:
                    if existing_ip.get('ip') == ip_info['ip']:
                        existing_ip['last_seen'] = max(existing_ip['last_seen'], ip_info['last_seen'])
                        ip_exists = True
                        break
                
                if not ip_exists:
                    formatted_users[user_id]['ips'].append(ip_info)
        
        return jsonify({
            'code': 200,
            'message': '获取用户历史成功',
            'data': {
                'users': formatted_users,
                'count': len(formatted_users)
            }
        })
    except Exception as e:
        logger.error(f"获取用户历史失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e),
            'data': None
        })

# ==================== 客户端拦截配置 ====================

@app.route('/api/intercept/config', methods=['GET'])
def api_get_intercept_config():
    """获取客户端拦截配置"""
    try:
        config = config_manager.load_config()
        client_filter = config.get('emby', {}).get('client_filter', {})
        
        # 返回标准化的拦截配置
        intercept_config = {
            'enable': client_filter.get('enable', False),
            'mode': client_filter.get('mode', 'blacklist'),
            'whitelist_devices': client_filter.get('allowed_devices', []),
            'blacklist_devices': client_filter.get('blocked_devices', []),
            'whitelist_ips': client_filter.get('allowed_ips', []),
            'blacklist_ips': client_filter.get('blocked_ips', [])
        }
        
        return jsonify({
            'code': 200,
            'message': '获取拦截配置成功',
            'data': intercept_config
        })
        
    except Exception as e:
        logger.error(f"获取拦截配置失败: {e}")
        return jsonify({
            'code': 500,
            'message': str(e),
            'data': None
        })

@app.route('/api/intercept/config', methods=['POST'])
def api_save_intercept_config():
    """保存客户端拦截配置"""
    try:
        new_intercept_config = request.get_json()
        
        if not new_intercept_config:
            return jsonify({
                'code': 400,
                'message': '无效的配置数据',
                'data': None
            })
        
        # 加载当前配置
        config = config_manager.load_config()
        
        # 确保emby配置段存在
        if 'emby' not in config:
            config['emby'] = {}
        
        # 更新客户端拦截配置
        config['emby']['client_filter'] = {
            'enable': bool(new_intercept_config.get('enable', False)),
            'mode': new_intercept_config.get('mode', 'blacklist'),
            'blocked_clients': new_intercept_config.get('blacklist_devices', []),  # 前端用devices字段
            'blocked_devices': new_intercept_config.get('blacklist_devices', []),
            'blocked_ips': new_intercept_config.get('blacklist_ips', []),
            'allowed_clients': new_intercept_config.get('whitelist_devices', []),
            'allowed_devices': new_intercept_config.get('whitelist_devices', []), 
            'allowed_ips': new_intercept_config.get('whitelist_ips', [])
        }
        
        # 保存配置
        config_manager.save_config(config)
        
        logger.info(f"✅ 客户端拦截配置已保存: enable={new_intercept_config.get('enable')}, mode={new_intercept_config.get('mode')}")
        
        return jsonify({
            'code': 200,
            'message': '拦截配置保存成功',
            'data': config['emby']['client_filter']
        })
        
    except Exception as e:
        logger.error(f"保存拦截配置失败: {e}")
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
    # 1. 初始化SQLite数据库
    try:
        db_manager = init_database()
        logger.info("🚀 SQLite 数据库初始化完成，程序性能大幅提升！")
    except Exception as e:
        logger.error(f"❌ SQLite 数据库初始化失败: {e}")
        logger.error("程序将退出，请检查数据库配置")
        exit(1)
    
    # 2. 初始化所有服务（在数据库初始化之后）
    initialize_services()
    logger.info("✅ 服务管理器初始化完成")
    
    # 3. 加载配置
    config = config_manager.load_config()
    logger.info(f"✅ 配置加载完成：Emby服务器={config.get('emby', {}).get('server', '未配置')}")
    
    # 4. 设置日志级别
    log_level = config.get('service', {}).get('log_level', 'INFO')
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    logger.info(f"日志级别设置为: {log_level}")
    
    # 5. 初始化客户端
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