#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
from flask import request, jsonify, Response, redirect
from models.config import ConfigManager
from services.strm_parser import StrmParserService
from services.alist_api import AlistApiService

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class EmbyProxyService:
    """Emby 反向代理服务"""

    def __init__(self, client_manager):
        self.client_manager = client_manager
        self.config_manager = ConfigManager()
        self.strm_parser_service = StrmParserService()
        self.alist_api_service = AlistApiService()
        self.emby_session = None
        
        # itemId 热路径缓存：减少重复 Items 查询
        self.item_path_cache = {}
        self.item_path_cache_ttl = 60  # 秒
        
        # 🚀 永久路径数据库：完全跳过Emby API查询
        from utils.item_path_db import ItemPathDatabase
        self.item_path_db = ItemPathDatabase()
        
        # 🚀 SQLite 数据库管理器：高性能数据存储
        from database.database import get_db_manager
        self.db = get_db_manager()
        
        # 兼容性：从旧的JSON文件迁移数据
        self.history_file = os.path.join(os.path.dirname(__file__), '..', 'config', 'user_history.json')
        self._migrate_user_history()
        
        # 连接超时设置（秒）
        self.connection_timeout = 300  # 5分钟

    def get_emby_session(self):
        """获取或创建 Emby 代理会话（支持连接池和重试）"""
        if self.emby_session is None:
            self.emby_session = requests.Session()

            # 配置重试策略
            retry_strategy = Retry(
                total=3,  # 最多重试 3 次
                backoff_factor=0.5,  # 重试间隔
                status_forcelist=[500, 502, 503, 504],  # 这些状态码会触发重试
                allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
            )

            # 配置 HTTP 和 HTTPS 适配器
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=20,  # 连接池大小
                pool_maxsize=20,
                pool_block=False
            )

            self.emby_session.mount("http://", adapter)
            self.emby_session.mount("https://", adapter)

        return self.emby_session

    def handle_playback_info(self, path, target_url):
        """处理 PlaybackInfo 请求，解析 .strm 文件并改写 MediaSource"""
        try:
            config = self.config_manager.load_config()

            logger.debug(f"🎵 拦截 PlaybackInfo 请求: {target_url}")

            # 转发请求到真实 Emby 服务器
            session = self.get_emby_session()
            ssl_verify = config['emby'].get('ssl_verify', False)

            headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'connection']}

            resp = session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                timeout=(10, 30),
                verify=ssl_verify
            )

            if resp.status_code != 200:
                logger.warning(f"⚠️ PlaybackInfo 请求失败: {resp.status_code}")
                return None

            # 解析响应
            body = resp.json()

            if not body.get('MediaSources') or len(body['MediaSources']) == 0:
                logger.warning(f"⚠️ PlaybackInfo 无 MediaSources")
                return None

            logger.debug(f"🎼 原始 MediaSources 数量: {len(body['MediaSources'])}")

            # 处理每个 MediaSource
            for i, source in enumerate(body['MediaSources']):
                source_path = source.get('Path', '')
                # 检查是否为 STRM 文件（更全面的检测）
                is_strm = (
                    source.get('IsRemote', False) or  # 远程文件
                    source_path.endswith('.strm') or  # 路径以.strm结尾
                    source.get('Container', '').lower() == 'strm' or  # 容器格式为strm
                    'original.strm' in target_url  # URL中包含original.strm
                )

                logger.debug(f"  MediaSource[{i}]: {source.get('Name', 'Unknown')}")
                logger.debug(f"    原始 Path: {source_path[:100] if source_path else 'N/A'}...")
                logger.debug(f"    原始 IsRemote: {source.get('IsRemote')}")
                if is_strm:
                    logger.info(f"  处理STRM文件: {source.get('Name', 'Unknown')}")

                if is_strm:
                    # 处理 .strm 文件
                    self.process_strm_media_source(source, config)
                else:
                    # 处理普通文件（可选的路径映射）
                    self.process_normal_media_source(source, config)

            # 返回修改后的响应
            return Response(
                json.dumps(body, ensure_ascii=False),
                status=resp.status_code,
                headers={'Content-Type': 'application/json;charset=utf-8'}
            )

        except Exception as e:
            logger.error(f"❌ 处理 PlaybackInfo 异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def process_strm_media_source(self, source, config):
        """处理 .strm 文件的 MediaSource"""
        try:
            source_path = source.get('Path', '')
            source_id = source.get('Id', source.get('Id', ''))

            logger.debug(f"🔄 开始处理 .strm 文件: {source.get('Name', 'Unknown')}")

            # 直接通过路径映射生成直链（去掉虚拟STRM构造，减少延迟）
            original_path = source_path
            logger.debug(f"📁 原始路径: {original_path}")

            mapped_url = self.alist_api_service.apply_path_mapping(original_path, config)
            if mapped_url == 'LOCAL_PROXY':
                logger.info(f"📁 本地STRM文件，跳过处理: {source.get('Name', 'Unknown')}")
                return  # 本地STRM文件不处理，保持原样
            elif not mapped_url:
                logger.error(f"❌ Alist路径映射失败")
                return
            real_url = mapped_url
            logger.debug(f"🔄 网盘STRM路径映射成功: {original_path[:50]}... -> {mapped_url[:50]}...")

            if not real_url:
                logger.error(f"❌ 无法解析 .strm 直链")
                return

            logger.debug(f"✅ 解析成功，直链: {real_url[:100]}...")

            # 步骤 3: 推断容器格式
            container = self.strm_parser_service.infer_container(real_url)
            logger.debug(f"📦 推断容器格式: {container}")

            # 步骤 4: 生成 ETag
            etag = self.strm_parser_service.generate_etag(real_url)
            logger.debug(f"🏷️ 生成 ETag: {etag}")

            # 步骤 5: 改写 MediaSource（核心逻辑）
            self.rewrite_media_source_for_strm(
                source, real_url, container, etag, source_id, config
            )

            logger.info(f"✅ STRM处理完成: {source.get('Name', 'Unknown')}")

        except Exception as e:
            logger.error(f"❌ 处理 .strm 文件异常: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def process_normal_media_source(self, source, config):
        """处理普通文件的 MediaSource（已移除路径映射功能）"""
        try:
            logger.info(f"处理普通媒体源: {source.get('Path', '')}")
            # 路径映射功能已移除，直接处理原始文件

            # 基本的直接播放设置
            source['SupportsDirectPlay'] = True
            source['SupportsDirectStream'] = True
            source['SupportsTranscoding'] = False

        except Exception as e:
            logger.error(f"处理普通 MediaSource 异常: {e}")

    # 已移除：modify_strm_item（不再修改 STRM Item）

    def rewrite_media_source_for_strm(self, source, real_url, container, etag, source_id, config):
        """为 .strm 文件改写 MediaSource（核心逻辑）"""
        try:
            original_name = source.get('Name', '')

            # 核心：按照要求改写 MediaSource 字段
            source['Id'] = source_id  # 保持或自定义
            source['Path'] = real_url  # 设为 real_url
            source['Protocol'] = 'Http'  # HTTP 协议
            source['MediaType'] = 'Video'  # 媒体类型
            source['Container'] = container  # 推断的容器
            source['SupportsDirectPlay'] = True  # 支持直接播放
            source['SupportsDirectStream'] = True  # 支持直接流
            source['SupportsTranscoding'] = False  # 禁用转码
            source['RequiresOpening'] = False  # 不需要打开
            source['IsRemote'] = True  # 是远程文件
            source['ETag'] = etag  # 可控的 ETag

            # 移除转码相关字段
            transcode_fields = ['TranscodingUrl', 'TranscodingSubProtocol', 'TranscodingContainer',
                                'TranscodingAudioChannels', 'TranscodingSampleRate']
            for field in transcode_fields:
                if field in source:
                    del source[field]

            # 修改文件名，移除 .strm 后缀
            if original_name.endswith('.strm'):
                new_name = original_name.replace('.strm', f'.{container}')
                source['Name'] = new_name
                logger.info(f"    修改名称: {original_name} => {new_name}")

            # 修改 DirectStreamUrl（可选）
            api_key = config['emby'].get('api_key', '')
            direct_stream_url = f"/Videos/{source_id}/stream.{container}?Static=true&MediaSourceId={source_id}"
            if api_key:
                direct_stream_url += f"&api_key={api_key}"
            source['DirectStreamUrl'] = direct_stream_url

            # 可选：填充 MediaStreams（基本信息）
            self.fill_basic_media_streams(source, container)

            # 可选：设置 RunTimeTicks（如果可以获取）
            # source['RunTimeTicks'] = duration * 10000000  # 微妙转毫微秒

            logger.debug(f"    ✅ STRM MediaSource 改写完成:")
            logger.debug(f"      Name: {source.get('Name')}")
            logger.debug(f"      Path: {source.get('Path')[:100]}...")
            logger.debug(f"      Protocol: {source.get('Protocol')}")
            logger.debug(f"      MediaType: {source.get('MediaType')}")
            logger.debug(f"      Container: {source.get('Container')}")
            logger.debug(f"      SupportsDirectPlay: {source.get('SupportsDirectPlay')}")
            logger.debug(f"      IsRemote: {source.get('IsRemote')}")
            logger.debug(f"      ETag: {source.get('ETag')}")

        except Exception as e:
            logger.error(f"改写 STRM MediaSource 异常: {e}")

    def fill_basic_media_streams(self, source, container):
        """填充基本的 MediaStreams 信息"""
        try:
            if 'MediaStreams' not in source:
                source['MediaStreams'] = []

            # 根据容器类型推断基本的音视频流信息
            # 这里只填充基本信息，实际播放时客户端会进一步解析

            # 视频流
            video_stream = {
                'Codec': container,
                'CodecTag': None,
                'Language': None,
                'ColorSpace': None,
                'Comment': None,
                'TimeBase': None,
                'CodecTimeBase': None,
                'Title': None,
                'Type': 'Video',
                'Index': -1,
                'IsDefault': True,
                'IsForced': False,
                'Height': None,  # 播放时会解析
                'Width': None,   # 播放时会解析
                'AverageFrameRate': None,
                'RealFrameRate': None,
                'Profile': None,
                'Type': 'Video',
                'AspectRatio': None,
                'Interlaced': False,
                'Level': None,
                'PixelFormat': None,
                'RefFrames': None,
                'IsAnamorphic': None,
                'ChannelLayout': None,
                'BitRate': None,
                'BitDepth': None,
                'SampleRate': None,
                'IsInterlaced': False,
                'Channels': None,
                'DisplayTitle': f"{container.upper()} - Default"
            }

            # 音频流（如果有）
            audio_stream = {
                'Codec': None,  # 会从实际流中解析
                'CodecTag': None,
                'Language': 'und',
                'ColorSpace': None,
                'Comment': None,
                'TimeBase': None,
                'CodecTimeBase': None,
                'Title': None,
                'Type': 'Audio',
                'Index': -1,
                'IsDefault': True,
                'IsForced': False,
                'Height': None,
                'Width': None,
                'AverageFrameRate': None,
                'RealFrameRate': None,
                'Profile': None,
                'Type': 'Audio',
                'AspectRatio': None,
                'Interlaced': False,
                'Level': None,
                'PixelFormat': None,
                'RefFrames': None,
                'IsAnamorphic': None,
                'ChannelLayout': None,
                'BitRate': None,
                'BitDepth': None,
                'SampleRate': None,
                'IsInterlaced': False,
                'Channels': 2,  # 默认立体声
                'DisplayTitle': "Default Audio"
            }

            source['MediaStreams'].append(video_stream)
            source['MediaStreams'].append(audio_stream)

        except Exception as e:
            logger.error(f"填充 MediaStreams 异常: {e}")

    def handle_emby_video_redirect(self, path):
        """处理 Emby 视频请求的 302 重定向"""
        try:
            config = self.config_manager.load_config()

            # 从 URL 中提取 item id
            # 典型路径:
            # - videos/{itemId}/stream.mkv
            # - videos/{itemId}/original.strm
            # - Items/{itemId}/Download
            parts = [p for p in path.split('/') if p]  # 过滤空字符串

            item_id = None
            for i, part in enumerate(parts):
                if part.lower() in ['videos', 'items'] and i + 1 < len(parts):
                    # 下一个部分应该是数字 ID 或 stream.xxx
                    potential_id = parts[i + 1]

                    # 如果是 stream.mkv 这种格式，直接提取数字
                    if potential_id.isdigit():
                        item_id = potential_id
                        break

                    # 如果包含 stream. 或 original.，可能是文件名，尝试从之前获取
                    # 例如：videos/50/stream.mkv
                    import re
                    match = re.match(r'^(\d+)', potential_id)
                    if match:
                        item_id = match.group(1)
                        break

            # 如果还没找到，尝试从 MediaSourceId 参数获取
            if not item_id:
                media_source_id = request.args.get('MediaSourceId') or request.args.get('mediaSourceId')
                if media_source_id:
                    if media_source_id.startswith('mediasource_'):
                        item_id = media_source_id.replace('mediasource_', '')
                    elif media_source_id.isdigit():
                        item_id = media_source_id

            if not item_id:
                logger.warning(f"无法从路径提取 item_id: {path}")
                return None

            logger.debug(f"提取到媒体项 ID: {item_id}")

            # 🚀 超级极速模式：检查永久路径数据库（完全跳过Emby API查询）
            if self.item_path_db.has(item_id):
                db_path = self.item_path_db.get(item_id)
                logger.info(f"⚡ 数据库命中: {item_id} → {os.path.basename(db_path)}")
                
                # 应用路径映射
                mapped_path = self.apply_path_mapping(db_path, config)
                if mapped_path == 'LOCAL_PROXY':
                    logger.info(f"📁 本地资源(数据库)，走代理播放: {os.path.basename(db_path)}")
                    return None  # 本地资源走代理
                elif mapped_path:
                    # 快速构建直链
                    direct_url = self._fast_build_direct_url(mapped_path, config)
                    if direct_url:
                        logger.info(f"✅ 302重定向(数据库): {os.path.basename(mapped_path)}")
                        return direct_url
            
            # 优先命中缓存，避免重复查询 Items 和网盘API
            cache_hit = False
            if item_id in self.item_path_cache:
                cached = self.item_path_cache[item_id]
                if cached and cached.get('expire', 0) > __import__('time').time():
                    cache_hit = True
                    # 直接从缓存返回最终直链，无需重新查询
                    direct_url = cached.get('direct_url')
                    file_name = cached.get('file_name')
                    if direct_url and file_name:
                        logger.info(f"✅ 302重定向(缓存): {file_name}")
                        return direct_url
                    
                    # 兼容旧缓存格式（没有direct_url字段）
                    emby_file_path = cached.get('emby_file_path')
                    mapped_path = cached.get('mapped_path')
                    if emby_file_path and mapped_path and file_name:
                        logger.debug(f"🗄️ Item缓存命中(旧格式): {item_id}")
                        # 若是网络直链直接返回
                        if emby_file_path.startswith(('http://', 'https://')):
                            logger.debug(f"检测到网络直链，直接返回: {emby_file_path[:100]}...")
                            return emby_file_path
                        # 快速获取直链（域名+路径，无API查询）
                        direct_url = self._fast_build_direct_url(mapped_path, config)
                        if direct_url:
                            # 更新缓存为新格式
                            cached['direct_url'] = direct_url
                            logger.info(f"✅ 302重定向(快速): {file_name}")
                            return direct_url
            
            # 没有缓存命中，需要查询 Emby API（这是最慢的路径）
            # 直接查询 Emby API 获取文件路径（绕过读取 .strm 文件，因为总是失败）
            emby_server = config['emby']['server'].rstrip('/')
            api_key = config['emby']['api_key']

            if not api_key:
                logger.error("Emby API Key 未配置")
                return None

            # 处理 MediaSourceId（可能包含 "mediasource_" 前缀）
            media_source_id = request.args.get('MediaSourceId') or request.args.get('mediaSourceId')
            query_item_id = item_id

            if media_source_id:
                logger.info(f"检测到 MediaSourceId: {media_source_id}")
                # 如果是 "mediasource_xxx" 格式，提取实际 ID
                if media_source_id.startswith("mediasource_"):
                    query_item_id = media_source_id.replace("mediasource_", "")
                    logger.info(f"从 MediaSourceId 提取 ID: {query_item_id}")

                # 使用 Items 查询接口（emby2Alist 的方法）
                # 正确格式：Items?Ids=xxx&Fields=Path,MediaSources&Limit=1&api_key=xxx
                # 判断服务器地址是否以 /emby 结尾
                if emby_server.endswith('/emby'):
                    item_url = f"{emby_server}/Items"
                else:
                    item_url = f"{emby_server}/emby/Items"

                params = {
                    'Ids': query_item_id,
                    'Fields': 'Path,MediaSources',
                    'Limit': 1,
                    'api_key': api_key
                }

                logger.debug(f"查询 Emby 项目: {item_url}?Ids={query_item_id}")

                # 使用会话
                session = self.get_emby_session()
                ssl_verify = config['emby'].get('ssl_verify', False)

                resp = session.get(item_url, params=params, timeout=(10, 30), verify=ssl_verify)

                if resp.status_code != 200:
                    logger.error(f"Emby API 请求失败: {resp.status_code}")
                    return None

                result = resp.json()

                if not result or not result.get('Items') or len(result['Items']) == 0:
                    logger.error(f"Emby API 返回空结果")
                    return None

                item_data = result['Items'][0]
                logger.debug(f"✅ 成功获取 Item 数据: {item_data.get('Name', 'Unknown')}")

                # 尝试多种方式获取文件路径
                emby_file_path = None

                # 优先从 MediaSources 中获取（支持多版本）
                if 'MediaSources' in item_data and item_data['MediaSources']:
                    media_source = item_data['MediaSources'][0]

                    # 如果有指定的 mediaSourceId，找到对应的源
                    if media_source_id and len(item_data['MediaSources']) > 1:
                        for ms in item_data['MediaSources']:
                            if ms.get('Id') == media_source_id or str(ms.get('Id')) == str(query_item_id):
                                media_source = ms
                                break

                    emby_file_path = media_source.get('Path')
                    logger.debug(f"从 MediaSources 获取路径")

                # 备用：从 Item 本身获取
                if not emby_file_path and 'Path' in item_data and item_data['Path']:
                    emby_file_path = item_data['Path']
                    logger.debug(f"从 Item.Path 获取路径")

                if not emby_file_path:
                    logger.error(f"无法获取文件路径: {item_id}")
                    logger.debug(f"Item 数据: {item_data.get('Name', 'Unknown')} - Type: {item_data.get('Type')}")
                    return None

                logger.debug(f"Emby 文件路径: {emby_file_path}")

                # 如果是网络直链，直接返回
                if emby_file_path.startswith(('http://', 'https://')):
                    logger.debug(f"检测到网络直链，直接返回: {emby_file_path[:100]}...")
                    return emby_file_path

                # 应用路径映射
                mapped_path = self.apply_path_mapping(emby_file_path, config)
                
                if mapped_path == 'LOCAL_PROXY':
                    logger.info(f"📁 本地资源，走代理播放: {os.path.basename(emby_file_path)}")
                    return None  # 返回None让上层继续走代理播放
                elif not mapped_path:
                    logger.warning(f"路径映射失败")
                    return None
                
                logger.debug(f"映射后的网盘路径: {mapped_path}")
                
                # 🚀 极速路径：优先尝试快速构建直链（域名+路径，无API查询）
                direct_url = self._fast_build_direct_url(mapped_path, config)
                
                if not direct_url:
                    # 如果快速构建失败，降级到标准方法（可能需要API查询）
                    logger.warning(f"⚠️ 快速直连构建失败，降级到API查询模式")
                    direct_url = self.get_direct_url_from_pan(mapped_path, config)
                
                if direct_url:
                    # 只有当获取直链成功时才写入Item路径缓存
                    # 这样可以避免重复查询Emby API和网盘API
                    try:
                        file_name = os.path.basename(mapped_path)
                        self.item_path_cache[item_id] = {
                            'emby_file_path': emby_file_path,
                            'mapped_path': mapped_path,
                            'file_name': file_name,
                            'direct_url': direct_url,  # 缓存最终直链
                            'expire': __import__('time').time() + self.item_path_cache_ttl
                        }
                        logger.debug(f"📦 Item路径+直链已缓存: {file_name}")
                        
                        # 🚀 保存到永久数据库，下次完全跳过Emby API查询
                        self.item_path_db.set(item_id, emby_file_path)
                    except Exception:
                        pass
                    
                    logger.info(f"✅ 302重定向成功: {os.path.basename(mapped_path)}")
                    return direct_url
                else:
                    logger.error(f"❌ 无法获取直链: {mapped_path}")
                    # 失败时不缓存，下次可以重试
                    return None

        except Exception as e:
            logger.error(f"❌ 处理重定向异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

        except Exception as e:
            logger.error(f"处理302重定向异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def apply_path_mapping(self, original_path, config):
        """应用路径映射，将本地路径转换为网络URL"""
        try:
            if not config['emby']['path_mapping']['enable']:
                logger.info(f"路径映射未启用，所有资源走本地代理")
                return 'LOCAL_PROXY'  # 特殊标识：本地代理播放

            from_prefix = config['emby']['path_mapping']['from']
            to_prefix = config['emby']['path_mapping']['to']

            # 统一路径分隔符（支持 Windows 和 Linux）
            emby_path_normalized = original_path.replace('\\', '/')
            from_path_normalized = from_prefix.replace('\\', '/')

            if not emby_path_normalized.startswith(from_path_normalized):
                logger.info(f"路径不匹配网盘前缀，走本地代理: {original_path[:50]}... (前缀: {from_prefix})")
                return 'LOCAL_PROXY'  # 特殊标识：本地代理播放

            # 替换路径前缀 - 这是网盘资源
            mapped_path = emby_path_normalized.replace(from_path_normalized, to_prefix, 1)
            logger.debug(f"✅ 网盘路径映射成功: {original_path[:50]}... => {mapped_path[:50]}...")

            return mapped_path

        except Exception as e:
            logger.error(f"❌ 路径映射异常: {e}")
            return 'LOCAL_PROXY'  # 异常时也走本地代理
    
    def _fast_build_direct_url(self, mapped_path, config):
        """
        快速构建直链（域名+路径+鉴权），无API查询
        适用于直链模式，极速返回
        """
        try:
            # 检查下载模式
            download_mode = config.get('123', {}).get('download_mode', 'direct')
            if download_mode != 'direct':
                return None
            
            # 检查URL鉴权配置
            auth_cfg = config.get('123', {}).get('url_auth', {})
            if not auth_cfg.get('enable'):
                return None
            
            custom_domains = auth_cfg.get('custom_domains', [])
            if not custom_domains:
                return None
            
            # 构建基础URL：自定义域名 + 文件路径
            domain = custom_domains[0]  # 使用第一个自定义域名
            
            # 处理路径：去掉挂载前缀（如/123），保留实际文件路径
            mount_path = config.get('123', {}).get('mount_path', '/123')
            if mapped_path.startswith(mount_path):
                file_path = mapped_path[len(mount_path):]
            else:
                file_path = mapped_path
            
            # 确保路径以/开头
            if not file_path.startswith('/'):
                file_path = '/' + file_path
            
            # 构建完整URL
            from urllib.parse import quote
            # URL编码路径，保留斜杠
            encoded_path = quote(file_path, safe='/')
            direct_url = f"https://{domain}{encoded_path}"
            
            # 添加URL鉴权
            from utils.url_auth import URLAuthManager
            auth_manager = URLAuthManager()
            secret_key = auth_cfg.get('secret_key', '')
            uid = auth_cfg.get('uid', '')
            expire_time = auth_cfg.get('expire_time', 3600)
            
            if secret_key and uid:
                authed_url = auth_manager.add_auth_to_url(direct_url, secret_key, uid, expire_time)
                
                # 🛡️ 智能域名健康检查（优化超时时间）
                if self._check_domain_health(domain):
                    logger.debug(f"⚡ 快速构建直链: {file_path[:50]}...")
                    return authed_url
                else:
                    logger.warning(f"⚠️ 域名健康检查失败，快速降级")
                    return None  # 返回None让上层降级到标准方法
            else:
                logger.warning(f"⚠️ URL鉴权配置不完整")
                return None
                
        except Exception as e:
            logger.error(f"❌ 快速构建直链失败: {e}")
            return None
    
    def _check_domain_health(self, domain):
        """智能域名健康检查（带缓存）"""
        try:
            import time
            import requests
            
            # 检查域名健康状态缓存
            cache_key = f"domain_health:{domain}"
            health_cache = self.db.get_direct_link(cache_key)
            
            current_time = time.time()
            
            # 如果有缓存且未过期，直接使用缓存结果
            if health_cache and health_cache['expire_time'] > current_time:
                is_healthy = health_cache['url'] == 'healthy'
                logger.debug(f"🎯 域名健康缓存命中: {domain} -> {'健康' if is_healthy else '不健康'}")
                return is_healthy
            
            # 执行快速健康检查
            try:
                # 使用更短的超时时间和更简单的检查
                test_url = f"https://{domain}/"
                logger.debug(f"🧪 域名健康检查: {domain}")
                
                response = requests.head(test_url, timeout=0.5, allow_redirects=False)
                # 任何响应（包括404）都说明域名可达
                is_healthy = True
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                # 超时或连接失败说明域名不可达
                is_healthy = False
            except Exception:
                # 其他异常也认为域名有问题
                is_healthy = False
            
            # 缓存健康状态（健康缓存5分钟，不健康缓存30秒）
            cache_duration = 300 if is_healthy else 30
            cache_value = 'healthy' if is_healthy else 'unhealthy'
            self.db.set_direct_link(cache_key, cache_value, cache_duration)
            
            logger.debug(f"📝 域名健康状态已缓存: {domain} -> {'健康' if is_healthy else '不健康'} ({cache_duration}s)")
            
            return is_healthy
            
        except Exception as e:
            logger.warning(f"⚠️ 域名健康检查异常: {e}")
            return False  # 异常时保守降级
    
    def get_direct_url_from_pan(self, alist_path, config):
        """从网盘获取文件直链（优先使用搜索）"""
        try:
            # 提取文件名
            import os
            file_name = os.path.basename(alist_path)
            
            # 解析路径，确定使用哪个网盘
            client, service_type, real_path = self.client_manager.get_client_for_path(alist_path, config)
            
            if not client:
                logger.error(f"❌ 无法找到对应的网盘客户端: {alist_path}")
                return None
            
            # 123网盘：支持双模式（Open API / 搜索） + URL鉴权
            if service_type == '123':
                # 使用统一的服务获取直链（包含鉴权）
                from services.pan123_service import Pan123Service
                pan123_service = Pan123Service(client, config)
                
                file_info = pan123_service.get_file_direct_link(file_name, alist_path)
                
                if file_info and file_info.get('raw_url'):
                    return file_info['raw_url']
                else:
                    logger.warning(f"⚠️ 未找到文件或获取直链失败")
                    return None
            
            # 其他网盘类型暂不支持
            logger.warning(f"⚠️ {service_type} 网盘暂不支持")
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取直链异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def extract_client_info(self, request):
        """从请求中提取客户端信息"""
        try:
            client_info = {}
            
            # 从查询参数中提取
            client_info['client'] = request.args.get('X-Emby-Client', '')
            client_info['device'] = request.args.get('X-Emby-Device-Name', '')
            client_info['device_id'] = request.args.get('X-Emby-Device-Id', '')
            client_info['version'] = request.args.get('X-Emby-Client-Version', '')
            client_info['token'] = request.args.get('X-Emby-Token', '')
            
            # 从请求头中提取
            if not client_info['client']:
                client_info['client'] = request.headers.get('X-Emby-Client', '')
            if not client_info['device']:
                client_info['device'] = request.headers.get('X-Emby-Device-Name', '')
            if not client_info['device_id']:
                client_info['device_id'] = request.headers.get('X-Emby-Device-Id', '')
            if not client_info['version']:
                client_info['version'] = request.headers.get('X-Emby-Client-Version', '')
            if not client_info['token']:
                client_info['token'] = request.headers.get('X-Emby-Token', '')
            
            # 从X-Emby-Authorization头中解析
            auth_header = request.headers.get('X-Emby-Authorization', '') or request.args.get('X-Emby-Authorization', '')
            if auth_header and not client_info['client']:
                import re
                # 解析格式: Emby Client="xxx", Device="xxx", DeviceId="xxx", Version="xxx"
                client_match = re.search(r'Client="([^"]*)"', auth_header)
                device_match = re.search(r'Device="([^"]*)"', auth_header)
                device_id_match = re.search(r'DeviceId="([^"]*)"', auth_header)
                version_match = re.search(r'Version="([^"]*)"', auth_header)
                
                if client_match:
                    client_info['client'] = client_match.group(1)
                if device_match:
                    client_info['device'] = device_match.group(1)
                if device_id_match:
                    client_info['device_id'] = device_id_match.group(1)
                if version_match:
                    client_info['version'] = version_match.group(1)
            
            # 添加请求信息
            client_info['ip'] = request.remote_addr
            client_info['user_agent'] = request.headers.get('User-Agent', '')
            client_info['path'] = request.path
            client_info['method'] = request.method
            
            return client_info
            
        except Exception as e:
            logger.error(f"❌ 提取客户端信息失败: {e}")
            return {}

    def check_client_access(self, client_info, config):
        """检查客户端访问权限"""
        try:
            # 获取客户端拦截配置
            client_filter = config.get('emby', {}).get('client_filter', {})
            
            # 🔍 调试：记录拦截配置状态
            logger.info(f"🛡️ 拦截检查 - enable: {client_filter.get('enable', False)}, mode: {client_filter.get('mode', 'none')}")
            
            if not client_filter.get('enable', False):
                logger.debug(f"✅ 拦截未启用，允许所有客户端")
                return True  # 未启用拦截，允许所有客户端
            
            client_name = client_info.get('client', '')
            device_name = client_info.get('device', '')
            ip_address = client_info.get('ip', '')
            
            # 🔍 调试：记录被检查的客户端信息
            logger.info(f"🔍 检查客户端 - Name: '{client_name}', Device: '{device_name}', IP: '{ip_address}'")
            
            # 黑名单模式
            if client_filter.get('mode') == 'blacklist':
                blocked_clients = client_filter.get('blocked_clients', [])
                blocked_devices = client_filter.get('blocked_devices', [])
                blocked_ips = client_filter.get('blocked_ips', [])
                
                # 🔍 调试：记录黑名单内容
                logger.info(f"📋 黑名单检查 - blocked_clients: {blocked_clients}, blocked_devices: {blocked_devices}, blocked_ips: {blocked_ips}")
                
                # 检查客户端名称
                if client_name.lower() in [c.lower() for c in blocked_clients]:
                    logger.warning(f"🚫 客户端被拦截: {client_name}")
                    return False
                
                # 检查设备名称  
                if device_name.lower() in [d.lower() for d in blocked_devices]:
                    logger.warning(f"🚫 设备被拦截: {device_name}")
                    return False
                
                # 检查IP地址
                if ip_address in blocked_ips:
                    logger.warning(f"🚫 IP被拦截: {ip_address}")
                    return False
                
                logger.debug(f"✅ 客户端通过黑名单检查: {client_name}")
                return True
            
            # 白名单模式
            elif client_filter.get('mode') == 'whitelist':
                allowed_clients = client_filter.get('allowed_clients', [])
                allowed_devices = client_filter.get('allowed_devices', [])
                allowed_ips = client_filter.get('allowed_ips', [])
                
                # 检查客户端名称
                if allowed_clients and client_info.get('client', '').lower() not in [c.lower() for c in allowed_clients]:
                    logger.warning(f"🚫 客户端不在白名单: {client_info.get('client')}")
                    return False
                
                # 检查设备名称
                if allowed_devices and client_info.get('device', '').lower() not in [d.lower() for d in allowed_devices]:
                    logger.warning(f"🚫 设备不在白名单: {client_info.get('device')}")
                    return False
                
                # 检查IP地址
                if allowed_ips and client_info.get('ip') not in allowed_ips:
                    logger.warning(f"🚫 IP不在白名单: {client_info.get('ip')}")
                    return False
                
                return True
            
            return True  # 默认允许
            
        except Exception as e:
            logger.error(f"❌ 检查客户端权限失败: {e}")
            return True  # 出错时默认允许

    def get_username_from_request(self, request):
        """从请求中获取用户名"""
        try:
            # 从请求参数中提取UserId
            user_id = request.args.get('UserId')
            logger.debug(f"🔍 从参数提取UserId: {user_id}")
            
            # 如果URL参数中没有，尝试从POST数据中获取
            if not user_id and request.is_json:
                try:
                    json_data = request.get_json()
                    if json_data:
                        user_id = json_data.get('UserId')
                        logger.debug(f"🔍 从POST数据提取UserId: {user_id}")
                except:
                    pass
            
            # 如果还没有，尝试从路径中提取
            if not user_id:
                import re
                # 匹配路径中的UserId，如 /Users/608e952ce5fb498592c30d75a2efefd9/Items
                path_match = re.search(r'/Users/([a-f0-9]{32})', request.path)
                if path_match:
                    user_id = path_match.group(1)
                    logger.debug(f"🔍 从路径提取UserId: {user_id} (路径: {request.path})")
            
            if user_id:
                # 使用缓存避免重复查询
                if not hasattr(self, '_user_cache'):
                    self._user_cache = {}
                    self._user_cache_time = {}
                
                import time
                current_time = time.time()
                
                # 检查缓存（5分钟有效期）
                if (user_id in self._user_cache and 
                    current_time - self._user_cache_time.get(user_id, 0) < 300):
                    return self._user_cache[user_id]
                
                # 查询用户信息
                config = self.config_manager.load_config()
                emby_server = config['emby']['server'].rstrip('/')
                api_key = config['emby']['api_key']
                
                session = self.get_emby_session()
                response = session.get(
                    f"{emby_server}/emby/Users/{user_id}?api_key={api_key}",
                    timeout=3,
                    verify=config['emby'].get('ssl_verify', False)
                )
                
                if response.status_code == 200:
                    user_info = response.json()
                    username = user_info.get('Name', 'Unknown User')
                    # 缓存结果
                    self._user_cache[user_id] = username
                    self._user_cache_time[user_id] = current_time
                    logger.debug(f"✅ 获取到用户名: {user_id} -> {username}")
                    return username
                else:
                    logger.debug(f"⚠️ 查询用户失败: {user_id}, HTTP {response.status_code}")
                        
            return 'Unknown User'
            
        except Exception as e:
            logger.debug(f"获取用户名异常: {e}")
            return 'Unknown User'
     
    def _get_real_username_from_emby(self, user_id):
        """从Emby API获取真实用户名"""
        try:
            config = self.config_manager.load_config()
            emby_server = config['emby']['server']
            api_key = config['emby']['api_key']
            
            if not emby_server or not api_key:
                return None
            
            # 调用Emby用户API
            import requests
            user_url = f"{emby_server}/emby/Users/{user_id}?api_key={api_key}"
            
            response = requests.get(user_url, timeout=2)
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('Name', '')
                if username:
                    logger.debug(f"📋 从Emby获取用户名: {username}")
                    return username
            
            return None
            
        except Exception as e:
            logger.debug(f"从Emby获取用户名失败: {e}")
            return None
    
    def _get_username_from_token(self, token):
        """从Token获取用户名"""
        try:
            config = self.config_manager.load_config()
            emby_server = config['emby']['server']
            
            if not emby_server or not token:
                return None
            
            # 使用Token调用用户信息API
            import requests
            auth_url = f"{emby_server}/emby/Users/Me?api_key={token}"
            
            response = requests.get(auth_url, timeout=2)
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('Name', '')
                if username:
                    logger.debug(f"🔑 从Token获取用户名: {username}")
                    return username
            
            return None
            
        except Exception as e:
            logger.debug(f"从Token获取用户名失败: {e}")
            return None

    def track_client_connection(self, client_info, request):
        """跟踪客户端连接"""
        try:
            import time
            current_time = time.time()
            
            # 🔍 调试：详细记录输入信息
            logger.info(f"🔧 跟踪输入 - client_info: {client_info}")
            
            # 过滤无效的客户端信息
            client_name = client_info.get('client', '').strip()
            device_name = client_info.get('device', '').strip()
            device_id = client_info.get('device_id', '').strip()
            
            # 🔍 调试：记录处理后的信息
            logger.info(f"📝 处理后信息 - client: '{client_name}', device: '{device_name}', device_id: '{device_id}'")
            
            # 如果客户端信息为空，跳过记录
            if not client_name or not device_id:
                logger.warning(f"⚠️ 客户端信息不完整，跳过跟踪 - client_name: '{client_name}', device_id: '{device_id}'")
                return
            
            # 生成客户端唯一标识（使用device_id作为主要标识）
            client_key = device_id
            
            # 获取用户名（增强版）
            username = self.get_username_from_request(request)
            
            # 🔍 调试：记录用户名获取结果
            logger.info(f"👤 获取到用户名: '{username}'")
            
            # 记录用户历史
            self.record_user_history(username, client_info)
            
            # 更新客户端连接信息（SQLite版本）
            success = self.db.add_client_connection(
                connection_id=client_key,
                user_id=username,
                device_id=device_id or 'Unknown',
                device_name=device_name or 'Unknown',
                client_name=client_name or 'Unknown',
                client_version=client_info.get('version', 'Unknown'),
                ip_address=client_info.get('ip', 'Unknown'),
                user_agent=client_info.get('user_agent', 'Unknown')
            )
            
            if success:
                logger.info(f"📱 客户端连接已记录: {client_name} ({device_name}) - {username}")
            
            # 定期清理过期连接
            self.cleanup_expired_clients()
                    
        except Exception as e:
            logger.error(f"❌ 跟踪客户端连接失败: {e}")

    def cleanup_expired_clients(self):
        """清理过期的客户端连接（SQLite版本）"""
        try:
            # 清理超过连接超时时间的连接
            expired_count = self.db.cleanup_expired_connections(self.connection_timeout)
            if expired_count > 0:
                logger.debug(f"🧹 已清理 {expired_count} 个过期客户端连接")
                    
        except Exception as e:
            logger.error(f"❌ 清理过期客户端失败: {e}")

    def record_user_history(self, user_id, client_info):
        """记录用户使用过的设备和IP（SQLite优化版本）"""
        try:
            if not user_id or user_id == 'Unknown User':
                return
            
            # 使用SQLite记录用户活动
            success = self.db.add_user_activity(
                user_id=str(user_id),
                device_id=client_info.get('device_id', 'Unknown'),
                device_name=client_info.get('device', 'Unknown'),
                client_name=client_info.get('client', 'Unknown'),
                ip_address=client_info.get('ip', None),
                user_agent=client_info.get('user_agent', None)
            )
            
            if success:
                logger.debug(f"📝 用户活动已记录: {user_id} - {client_info.get('client', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"❌ 记录用户历史失败: {e}")

    def _migrate_user_history(self):
        """从旧JSON文件迁移用户历史数据到SQLite"""
        try:
            if os.path.exists(self.history_file):
                logger.info("🔄 发现旧的用户历史记录文件，开始迁移到SQLite...")
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    migrated = 0
                    for user_id, user_data in data.items():
                        # 迁移设备记录
                        for device in user_data.get('devices', []):
                            success = self.db.add_user_activity(
                                user_id=str(user_id),
                                device_id=device.get('device_id', 'Unknown'),
                                device_name=device.get('device', 'Unknown'),
                                client_name=device.get('client', 'Unknown'),
                                ip_address=None,
                                user_agent=None
                            )
                            if success:
                                migrated += 1
                        
                        # 迁移IP记录
                        for ip_info in user_data.get('ips', []):
                            success = self.db.add_user_activity(
                                user_id=str(user_id),
                                device_id=None,
                                device_name=None,
                                client_name=None,
                                ip_address=ip_info.get('ip'),
                                user_agent=ip_info.get('user_agent', None)
                            )
                            if success:
                                migrated += 1
                    
                    logger.info(f"✅ 用户历史迁移完成: {migrated} 条记录")
                    
                    # 备份并删除旧文件
                    backup_file = self.history_file + '.bak'
                    os.rename(self.history_file, backup_file)
                    logger.info(f"📦 旧历史文件已备份为: {backup_file}")
        except Exception as e:
            logger.warning(f"⚠️ 迁移用户历史记录失败: {e}")

    @property
    def user_history(self):
        """获取用户历史记录（兼容性属性）"""
        return self.db.get_unique_users()

    @property  
    def connected_clients(self):
        """获取连接的客户端（兼容性属性）"""
        return self.db.get_active_connections(self.connection_timeout)

    def proxy_request(self, path=''):
        """Emby API 反向代理（独立端口，无需 /emby 前缀）"""
        # 缓存配置，避免每次都加载（5秒缓存）
        if not hasattr(self, '_config_cache') or not hasattr(self, '_config_cache_time'):
            self._config_cache = None
            self._config_cache_time = 0
        
        current_time = __import__('time').time()
        if current_time - self._config_cache_time > 5:
            self._config_cache = self.config_manager.load_config()
            self._config_cache_time = current_time
        
        config = self._config_cache

        if not config['emby']['enable']:
            return jsonify({'error': 'Emby proxy is not enabled'}), 503

        # 提取客户端信息（对所有请求进行拦截检查）
        client_info = self.extract_client_info(request)
        
        # 🛡️ 对所有请求都进行客户端拦截检查
        if not self.check_client_access(client_info, config):
            logger.warning(f"🚫 客户端访问被拒绝: {client_info.get('client', 'Unknown')} ({client_info.get('ip', 'Unknown IP')})")
            return jsonify({'error': 'Access denied'}), 403
        
        # 只对重要请求进行客户端跟踪（避免过多跟踪）
        path_lower = request.path.lower()
        is_critical_request = any(keyword in path_lower for keyword in 
            ['/playbackinfo', '/playing', '/stream', '/videos/', '/download'])
        
        if is_critical_request:

            # 🔍 捕获所有重要的客户端活动
            should_track = (
                # 播放相关请求（核心跟踪）
                '/PlaybackInfo' in request.path or
                '/Sessions/Playing' in request.path or
                # 用户查询请求
                ('/Users/' in request.path and 'UserId=' in request.query_string.decode('utf-8', errors='ignore')) or
                # 媒体项查询（包含用户ID）
                ('/Items/' in request.path and 'UserId=' in request.query_string.decode('utf-8', errors='ignore'))
            )
            
            # 🔍 调试：记录跟踪决策
            logger.info(f"🔍 跟踪检查 - Path: {request.path[:50]}, Track: {should_track}")
            
            if should_track:
                logger.info(f"📱 开始跟踪客户端连接...")
                self.track_client_connection(client_info, request)
            else:
                logger.debug(f"⏭️ 跳过跟踪: {request.path}")

        emby_server = config['emby']['server'].rstrip('/')

        # 构建目标 URL
        if path:
            target_url = f"{emby_server}/{path}"
        else:
            target_url = emby_server

        # 添加查询参数
        if request.query_string:
            target_url += '?' + request.query_string.decode('utf-8')

        # 限制日志输出频率，避免刷屏
        current_time = __import__('time').time()
        if not hasattr(self, '_last_log_time'):
            self._last_log_time = {}
        
        # 为不同类型的请求设置不同的日志频率
        request_key = f"{request.method}_{request.path.split('?')[0]}"
        last_time = self._last_log_time.get(request_key, 0)
        
        # 图片请求：30秒输出一次，其他请求：10秒输出一次
        log_interval = 30 if '/Images/' in request.path else 10
        
        if current_time - last_time > log_interval:
            # 只对重要请求输出日志
            if any(keyword in request.path.lower() for keyword in ['/playbackinfo', '/stream', '/download', '/videos/']):
                logger.info(f"[Emby Proxy] {request.method} {target_url[:100]}...")
            else:
                logger.debug(f"[Emby Proxy] {request.method} {target_url[:100]}...")
            self._last_log_time[request_key] = current_time

        # 路径小写（用于匹配）
        path_lower = request.path.lower()

        # 已移除: Items 请求特殊处理，直接走普通代理以减少延迟

        # 特殊处理1: PlaybackInfo 请求 - 修改响应，让 strm 支持直接播放
        if '/playbackinfo' in path_lower and request.method == 'POST':
            if config['emby'].get('modify_playback_info', False):
                try:
                    result = self.handle_playback_info(path, target_url)
                    if result:
                        return result
                    else:
                        logger.warning(f"⚠️ PlaybackInfo 处理返回 None，回退到普通代理")
                except Exception as e:
                    logger.error(f"❌ 处理 PlaybackInfo 失败: {e}, 回退到普通代理")
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.debug(f"⏭️ PlaybackInfo拦截已禁用，直接代理转发（速度更快）")

        # 特殊处理2: /Videos 路径的 302 重定向
        # 匹配 /videos/xxx/stream.xxx 或 /videos/xxx/xxx.strm 或 /Videos/xxx/Download
        query_str = request.query_string.decode('utf-8').lower()
        is_video_request = (
            '/videos/' in path_lower and (
                '/stream' in path_lower or
                'stream.' in path_lower or  # 匹配 stream.mkv 等
                '.strm' in path_lower or
                '/download' in path_lower or
                'mediasourceid=' in query_str or
                'static=true' in query_str  # DirectStreamUrl 特征
            )
        )

        if config['emby']['redirect_enable'] and is_video_request:
            try:
                # 尝试获取直链并 302 重定向
                direct_url = self.handle_emby_video_redirect(path)
                if direct_url:
                    return redirect(direct_url, code=302)
                elif direct_url is None:
                    # None表示本地资源，直接走代理播放，不输出警告
                    logger.debug(f"🏠 本地资源直接走代理播放")
                else:
                    logger.warning(f"⚠️ 网盘资源获取直链失败，回退到普通代理")
            except Exception as e:
                logger.error(f"❌ 302 重定向失败: {e}, 回退到普通代理")

        # 普通代理请求
        try:
            # 准备请求头
            headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'connection']}

            # 获取会话
            session = self.get_emby_session()

            # 是否验证 SSL 证书
            ssl_verify = config['emby'].get('ssl_verify', False)

            # 移除健康检查，提高响应速度
            # 让请求失败时自然报错，而不是提前检查

            # 发起请求
            resp = session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                stream=True,
                timeout=(10, 30),  # 减少超时时间，避免长时间等待
                verify=ssl_verify  # 根据配置决定是否验证 SSL 证书
            )

            # 构建响应
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
            response_headers = [(name, value) for name, value in resp.raw.headers.items()
                               if name.lower() not in excluded_headers]

            # 返回响应
            return Response(resp.iter_content(chunk_size=8192),
                           status=resp.status_code,
                           headers=response_headers)

        except requests.exceptions.Timeout as e:
            logger.error(f"代理请求超时: {target_url[:100]}")
            return jsonify({'error': 'Request timeout'}), 504

        except requests.exceptions.ConnectionError as e:
            logger.error(f"代理请求连接失败: {target_url[:100]}")
            return jsonify({'error': 'Connection failed'}), 503

        except Exception as e:
            logger.error(f"代理请求失败: {e}")
            return jsonify({'error': str(e)}), 500