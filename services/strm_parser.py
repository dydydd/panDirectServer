#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import requests
import re
from urllib.parse import urlparse, unquote
from models.config import ConfigManager

logger = logging.getLogger(__name__)

class StrmParserService:
    """STRM 文件解析服务"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def read_strm_file(self, file_path):
        """读取 .strm 文件内容，获取原始 URL"""
        try:
            if not file_path or not file_path.endswith('.strm'):
                logger.warning(f"文件不是 .strm 格式: {file_path}")
                return None

            # 如果是本地文件，直接读取
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    logger.info(f"读取本地 .strm 文件: {file_path}")
                    return content

            # 如果是网络 URL，尝试获取内容
            if file_path.startswith(('http://', 'https://')):
                logger.info(f"读取网络 .strm 文件: {file_path}")
                resp = self.session.get(file_path, timeout=10)
                if resp.status_code == 200:
                    return resp.text.strip()
                else:
                    logger.error(f"获取网络 .strm 文件失败: {resp.status_code}")
                    return None

            logger.error(f"无法读取 .strm 文件: {file_path}")
            return None

        except Exception as e:
            logger.error(f"读取 .strm 文件异常: {e}")
            return None

    def parse_strm_url(self, strm_url):
        """解析 .strm URL，得到真实播放直链"""
        try:
            if not strm_url:
                return None

            logger.info(f"开始解析 .strm URL: {strm_url}")

            # 直接的直链（以 http/https 开头）
            if strm_url.startswith(('http://', 'https://')):
                # 检查是否是已知的网盘分享链接，需要进一步解析
                real_url = self.parse_cloud_url(strm_url)
                if real_url:
                    return real_url

                # 如果是直接的媒体文件链接，直接返回
                if self.is_direct_media_url(strm_url):
                    return strm_url

                # 其他情况尝试访问获取重定向
                return self.resolve_redirect_url(strm_url)

            # 其他协议（rtsp, rtmp 等）
            if strm_url.startswith(('rtsp://', 'rtmp://', 'magnet://')):
                return strm_url

            logger.warning(f"不支持的 .strm URL 格式: {strm_url}")
            return None

        except Exception as e:
            logger.error(f"解析 .strm URL 异常: {e}")
            return None

    def parse_cloud_url(self, url):
        """解析云盘分享链接，获取直链"""
        try:
            # 如果是已知的直链格式，直接返回
            if self.is_direct_media_url(url):
                return url

            logger.info(f"不支持的云盘分享链接格式: {url}")
            return None

        except Exception as e:
            logger.error(f"解析云盘 URL 异常: {e}")
            return None

    def is_direct_media_url(self, url):
        """判断是否是直接的媒体文件 URL"""
        try:
            # 检查 URL 路径是否以媒体文件扩展名结尾
            parsed = urlparse(url)
            path = unquote(parsed.path.lower())

            media_extensions = {
                '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
                '.m4v', '.3gp', '.ts', '.mts', '.m2ts', '.vob', '.f4v',
                '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'
            }

            # 检查文件扩展名
            for ext in media_extensions:
                if path.endswith(ext):
                    return True

            # 检查是否包含已知的 CDN 域名
            cdn_domains = [
                'cdn', 'stream', 'media', 'video', 'download',
                'aliyuncs', 'qbox.me', 'qiniu', 'tencent-cloud',
                '115cdn', '123pan', 'larksuitecdn'
            ]

            domain = parsed.netloc.lower()
            for cdn in cdn_domains:
                if cdn in domain:
                    return True

            return False

        except Exception:
            return False

    def resolve_redirect_url(self, url, max_redirects=5):
        """解析重定向 URL，获取最终直链"""
        try:
            logger.info(f"解析重定向 URL: {url}")

            # 不自动跟随重定向，手动获取 Location 头
            resp = self.session.head(url, allow_redirects=False, timeout=10)

            if resp.status_code in [301, 302, 303, 307, 308]:
                redirect_url = resp.headers.get('Location')
                if redirect_url:
                    logger.info(f"重定向到: {redirect_url}")

                    # 递归处理多重重定向
                    if max_redirects > 0:
                        return self.resolve_redirect_url(redirect_url, max_redirects - 1)
                    else:
                        return redirect_url

            # 如果没有重定向，尝试 GET 请求获取最终链接
            resp = self.session.get(url, stream=True, timeout=10)
            if resp.ok:
                # 检查响应是否是媒体文件
                content_type = resp.headers.get('content-type', '').lower()
                if 'video' in content_type or 'audio' in content_type:
                    return url

                # 检查是否是 m3u8 播放列表
                if 'application/vnd.apple.mpegurl' in content_type or url.endswith('.m3u8'):
                    return url

            return url

        except Exception as e:
            logger.error(f"解析重定向 URL 异常: {e}")
            return url

  
    def infer_container(self, url):
        """从 URL 推断容器格式"""
        try:
            parsed = urlparse(url)
            path = unquote(parsed.path.lower())

            container_map = {
                '.mp4': 'mp4',
                '.mkv': 'mkv',
                '.avi': 'avi',
                '.mov': 'mov',
                '.wmv': 'wmv',
                '.flv': 'flv',
                '.webm': 'webm',
                '.m4v': 'm4v',
                '.3gp': '3gp',
                '.ts': 'mpegts',
                '.mts': 'mpegts',
                '.m2ts': 'mpegts',
                '.m3u8': 'hls',
                '.mp3': 'mp3',
                '.wav': 'wav',
                '.flac': 'flac',
                '.aac': 'aac',
                '.ogg': 'ogg',
                '.m4a': 'm4a'
            }

            for ext, container in container_map.items():
                if path.endswith(ext):
                    return container

            # 如果无法推断，默认返回 mp4
            return 'mp4'

        except Exception:
            return 'mp4'

    def generate_etag(self, url):
        """生成可控的 ETag"""
        try:
            import hashlib
            # 使用 URL 的哈希值作为 ETag
            hash_obj = hashlib.md5(url.encode('utf-8'))
            return f'"{hash_obj.hexdigest()[:16]}"'
        except Exception:
            return '"strm-media"'

    def extract_media_info_from_filename(self, filename):
        """从文件名中提取媒体信息"""
        try:
            import re

            # 移除 .strm 后缀
            clean_name = filename.replace('.strm', '')

            # 匹配常见的命名模式
            # 示例：仙逆.2023.S01E06.第6集.2160p.WEB-DL.H.265.mkv

            info = {
                'title': clean_name,  # 默认使用完整文件名
                'year': None,
                'season': None,
                'episode': None,
                'episode_title': None,
                'resolution': None,
                'source': None,
                'video_codec': None,
                'audio_codec': None
            }

            # 提取年份
            year_match = re.search(r'\b(19|20)\d{2}\b', clean_name)
            if year_match:
                info['year'] = year_match.group()

            # 提取季数和集数
            season_episode_match = re.search(r'S(\d{1,2})E(\d{1,2})', clean_name, re.IGNORECASE)
            if season_episode_match:
                info['season'] = int(season_episode_match.group(1))
                info['episode'] = int(season_episode_match.group(2))

            # 提取中文集数（第X集）
            chinese_episode_match = re.search(r'第(\d+)集', clean_name)
            if chinese_episode_match:
                info['episode_title'] = f"第{chinese_episode_match.group(1)}集"

            # 提取分辨率
            resolution_patterns = [
                (r'2160p|4K', '2160p'),
                (r'1440p|2K', '1440p'),
                (r'1080p', '1080p'),
                (r'720p', '720p'),
                (r'480p', '480p')
            ]

            for pattern, resolution in resolution_patterns:
                if re.search(pattern, clean_name, re.IGNORECASE):
                    info['resolution'] = resolution
                    break

            # 提取来源
            source_patterns = [
                (r'WEB-?DL', 'WEB-DL'),
                (r'BluRay|BDRip', 'BluRay'),
                (r'DVD|DVDRip', 'DVD'),
                (r'HDTV', 'HDTV'),
                (r'WEBRip', 'WEBRip')
            ]

            for pattern, source in source_patterns:
                if re.search(pattern, clean_name, re.IGNORECASE):
                    info['source'] = source
                    break

            # 提取视频编码
            video_codec_patterns = [
                (r'H\.?265|HEVC', 'H.265'),
                (r'H\.?264|AVC', 'H.264'),
                (r'VP9', 'VP9'),
                (r'AV1', 'AV1'),
                (r'Xvid', 'XviD')
            ]

            for pattern, codec in video_codec_patterns:
                if re.search(pattern, clean_name, re.IGNORECASE):
                    info['video_codec'] = codec
                    break

            # 提取音频编码
            audio_codec_patterns = [
                (r'DTS', 'DTS'),
                (r'AC3|DD', 'AC3'),
                (r'AAC', 'AAC'),
                (r'MP3', 'MP3'),
                (r'FLAC', 'FLAC')
            ]

            for pattern, codec in audio_codec_patterns:
                if re.search(pattern, clean_name, re.IGNORECASE):
                    info['audio_codec'] = codec
                    break

            # 提取标题（去除技术信息）
            title = clean_name

            # 移除年份
            if info['year']:
                title = title.replace(info['year'], '').strip()

            # 移除季集信息
            title = re.sub(r'S\d{1,2}E\d{1,2}', '', title, flags=re.IGNORECASE).strip()
            title = re.sub(r'第\d+集', '', title).strip()

            # 移除分辨率信息
            if info['resolution']:
                title = re.sub(info['resolution'], '', title, flags=re.IGNORECASE).strip()

            # 移除来源信息
            if info['source']:
                title = re.sub(info['source'], '', title, flags=re.IGNORECASE).strip()

            # 移除编码信息
            if info['video_codec']:
                title = re.sub(info['video_codec'], '', title, flags=re.IGNORECASE).strip()

            # 清理多余的分隔符
            title = re.sub(r'[._\-]+', ' ', title).strip()

            if title:
                info['title'] = title

            logger.info(f"从文件名提取媒体信息: {filename}")
            logger.info(f"  标题: {info['title']}")
            logger.info(f"  年份: {info['year']}")
            logger.info(f"  季/集: S{info['season'] or '?'}E{info['episode'] or '?'}")
            logger.info(f"  分辨率: {info['resolution']}")
            logger.info(f"  来源: {info['source']}")
            logger.info(f"  视频编码: {info['video_codec']}")

            return info

        except Exception as e:
            logger.error(f"提取媒体信息异常: {e}")
            return {
                'title': filename.replace('.strm', ''),
                'year': None,
                'season': None,
                'episode': None,
                'episode_title': None,
                'resolution': None,
                'source': None,
                'video_codec': None,
                'audio_codec': None
            }