#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from pathlib import Path
from p123client import P123Client

logger = logging.getLogger(__name__)

class ClientManager:
    """客户端管理器"""

    def __init__(self):
        self.clients = {
            '123': None
        }
        self.TOKEN_123_FILE = Path('config/123-token.txt')

    def init_clients(self, config):
        """初始化网盘客户端"""
        # 初始化 123 客户端
        if config.get('123', {}).get('enable'):
            try:
                logger.info("🔄 开始初始化123网盘客户端...")
                
                # 检查必要的依赖
                try:
                    import h2
                    logger.info("✅ h2 依赖检查通过")
                except ImportError:
                    logger.error("❌ 缺少 h2 依赖，请运行: pip install h2==4.1.0")
                    self.clients['123'] = None
                    return
                
                if config['123'].get('token'):
                    # 保存 token 到文件
                    logger.info("📝 使用token方式初始化123客户端")
                    self.TOKEN_123_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.TOKEN_123_FILE, 'w', encoding='utf-8') as f:
                        f.write(config['123'].get('token', ''))
                    self.clients['123'] = P123Client(self.TOKEN_123_FILE)
                elif config['123'].get('passport') and config['123'].get('password'):
                    logger.info("📝 使用账号密码方式初始化123客户端")
                    self.clients['123'] = P123Client(
                        passport=config['123'].get('passport', ''),
                        password=config['123'].get('password', '')
                    )
                elif config['123'].get('client_id') and config['123'].get('client_secret'):
                    logger.info("📝 使用client_id/client_secret方式初始化123客户端")
                    logger.info(f"Client ID: {config['123'].get('client_id', '')[:8]}...")
                    self.clients['123'] = P123Client(
                        client_id=config['123'].get('client_id', ''),
                        client_secret=config['123'].get('client_secret', '')
                    )
                else:
                    logger.warning("⚠️ 未配置有效的123网盘认证信息，请在前端配置以下任一方式：")
                    logger.warning("  - Token 文件路径")
                    logger.warning("  - 用户名和密码")
                    logger.warning("  - 应用ID (client_id) 和应用密钥 (client_secret)")
                    logger.warning("跳过123客户端初始化，避免二维码登录")
                    self.clients['123'] = None
                    return
                
                # 测试客户端连接
                if self.clients['123']:
                    logger.info("🧪 测试123客户端连接...")
                    # 尝试调用一个简单的API来测试连接
                    try:
                        test_result = self.clients['123'].fs_list_new({'SearchData': 'test', 'limit': 1})
                        if test_result and test_result.get('code') == 0:
                            logger.info("✅ 123 客户端连接测试成功")
                        else:
                            logger.warning(f"⚠️ 123 客户端连接测试失败: {test_result}")
                    except Exception as test_e:
                        logger.warning(f"⚠️ 123 客户端连接测试异常: {test_e}")
                
                logger.info("✅ 123 客户端初始化完成")
            except Exception as e:
                logger.error(f"❌ 123 客户端初始化失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.clients['123'] = None

    def get_client_for_path(self, path, config):
        """根据路径获取对应的客户端"""
        mount_path = config.get('123', {}).get('mount_path', '/123')
        if path.startswith(mount_path):
            return self.clients['123'], '123', path[len(mount_path):]
        
        logger.warning(f"❌ 未匹配任何网盘: {path}")
        return None, None, path

    def get_status(self):
        """获取客户端状态"""
        return {
            '123': {
                'connected': self.clients['123'] is not None,
                'message': '已连接' if self.clients['123'] else '未连接'
            }
        }
    
    def get_123_file_by_open_api(self, file_name):
        """使用 123 Open API 直接获取直链（最快）"""
        client = self.clients.get('123')
        if not client:
            logger.error("123 客户端未初始化")
            return None
        
        try:
            logger.info(f"🚀 使用 Open API 获取直链: {file_name}")
            
            # 第一步：搜索文件获取 fileID
            search_result = client.fs_list_new({
                'SearchData': file_name,
                'limit': 10
            })
            
            if not search_result or search_result.get('code') != 0:
                logger.warning(f"⚠️ 搜索失败")
                return None
            
            data = search_result.get('data', {})
            items = data.get('InfoList', [])
            
            logger.info(f"🔍 搜索到 {len(items)} 个结果")
            
            # 查找完全匹配的文件
            file_id = None
            matched_item = None
            for item in items:
                if item.get('FileName') == file_name and item.get('Type') == 0:
                    file_id = item['FileId']
                    matched_item = item
                    logger.info(f"✅ 找到文件: {file_name}, FileId={file_id}")
                    break
            
            if not file_id:
                logger.warning(f"⚠️ 未找到匹配的文件")
                return None
            
            # 第二步：使用 Open API 获取直链（需要鉴权）
            logger.info(f"📡 调用 Open API 获取直链... (fileID={file_id})")
            
            # 检查是否有 client_id 和 client_secret（Open API 需要）
            # 如果使用 passport/password 登录，需要先获取 access_token
            try:
                # 使用 p123client 的 Open API 方法
                # 注意：需要使用 P123OpenClient 或确保客户端初始化时使用了 client_id/client_secret
                import requests
                
                # 获取 access_token
                token = None
                if hasattr(client, 'access_token'):
                    token = client.access_token
                elif hasattr(client, 'token'):
                    token = client.token
                    
                if not token:
                    logger.error(f"❌ 无法获取 access_token，Open API 需要鉴权")
                    logger.info(f"💡 提示：请使用 client_id/client_secret 或 token 登录")
                    return None
                
                # 调用 Open API
                url = f"https://open-api.123pan.com/api/v1/direct-link/url?fileID={file_id}"
                headers = {
                    'Content-Type': 'application/json',
                    'Platform': 'open_platform',
                    'Authorization': f'Bearer {token}'
                }
                
                resp = requests.get(url, headers=headers, timeout=10)
                direct_link_result = resp.json()
                
                logger.info(f"Open API 响应: code={direct_link_result.get('code')}, message={direct_link_result.get('message')}")
                
                if direct_link_result and direct_link_result.get('code') == 0:
                    direct_url = direct_link_result.get('data', {}).get('url')
                    if direct_url:
                        logger.info(f"✅ Open API 获取直链成功: {direct_url[:100]}...")
                        return {
                            'name': matched_item['FileName'],
                            'size': matched_item.get('Size', 0),
                            'is_dir': False,
                            'modified': matched_item.get('CreateAt', ''),
                            'raw_url': direct_url,
                            'sign': '',
                            'header': {}
                        }
                
                logger.warning(f"⚠️ Open API 返回异常: {direct_link_result.get('message', 'Unknown')}")
                return None
                
            except Exception as e:
                logger.error(f"❌ 调用 Open API 异常: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None
            
        except Exception as e:
            logger.error(f"❌ Open API 异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def get_123_file_by_search(self, file_name):
        """使用搜索 + download_url 获取直链（兼容方法）"""
        client = self.clients.get('123')
        if not client:
            logger.error("123 客户端未初始化")
            return None
        
        try:
            logger.info(f"🔍 使用搜索API获取文件: {file_name}")
            
            # 使用搜索 API
            search_result = client.fs_list_new({
                'SearchData': file_name,
                'limit': 20
            })
            
            if search_result and search_result.get('code') == 0:
                data = search_result.get('data', {})
                items = data.get('InfoList', [])
                
                logger.info(f"🔍 搜索到 {len(items)} 个结果")
                
                # 查找完全匹配的文件
                for item in items:
                    if item.get('FileName') == file_name and item.get('Type') == 0:
                        logger.info(f"✅ 搜索命中: {file_name}")
                        # 获取下载链接
                        file_id = item['FileId']
                        download_url = client.download_url({'FileID': file_id})
                        
                        return {
                            'name': item['FileName'],
                            'size': item.get('Size', 0),
                            'is_dir': False,
                            'modified': item.get('CreateAt', ''),
                            'raw_url': download_url,
                            'sign': '',
                            'header': {}
                        }
                
                logger.warning(f"⚠️ 搜索结果中未找到完全匹配")
                return None
            else:
                logger.warning(f"⚠️ 搜索API返回异常")
                return None
        except Exception as e:
            logger.error(f"❌ 搜索异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def get_123_file_info(self, file_name, config):
        """智能获取123网盘文件信息（支持双模式切换）"""
        use_open_api = config.get('123', {}).get('use_open_api', True)
        fallback = config.get('123', {}).get('fallback_to_search', True)
        
        file_info = None
        
        # 优先使用 Open API（更快更稳定）
        if use_open_api:
            logger.info(f"🚀 模式：Open API 直链")
            file_info = self.get_123_file_by_open_api(file_name)
            
            # 如果失败且启用了降级，尝试搜索方法
            if not file_info and fallback:
                logger.info(f"⚠️ Open API 失败，降级到搜索模式")
                file_info = self.get_123_file_by_search(file_name)
        else:
            # 使用搜索方法
            logger.info(f"🔍 模式：搜索 + download_url")
            file_info = self.get_123_file_by_search(file_name)
        
        return file_info