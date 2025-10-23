#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CacheManager:
    """缓存管理器"""

    def __init__(self):
        # 直链缓存：{alist_path: {url: xxx, expire: timestamp}}
        self.direct_link_cache = {}
        # 路径到FileId的缓存：{path: file_id}
        self.path_id_cache = {}
        # 缓存持久化文件
        self.PATH_CACHE_FILE = Path('config/path_cache.json')
        # 加载持久化缓存
        self.load_path_cache()

    def load_path_cache(self):
        """从磁盘加载路径缓存。"""
        try:
            if self.PATH_CACHE_FILE.exists():
                with open(self.PATH_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.path_id_cache.update({str(k): v for k, v in data.items()})
                        logger.info(f"已加载路径缓存: {len(self.path_id_cache)} 条")
        except Exception as e:
            logger.warning(f"加载路径缓存失败: {e}")
    
    def save_path_cache(self):
        """将路径缓存保存到磁盘。"""
        try:
            self.PATH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.PATH_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.path_id_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存路径缓存失败: {e}")

    def get_direct_link(self, path):
        """获取缓存的直链"""
        return self.direct_link_cache.get(path)

    def set_direct_link(self, path, url, expire_time=3600):
        """设置直链缓存"""
        self.direct_link_cache[path] = {
            'url': url,
            'expire': time.time() + expire_time
        }

    def is_direct_link_valid(self, path):
        """检查直链缓存是否有效"""
        cached = self.direct_link_cache.get(path)
        if cached and time.time() < cached['expire']:
            return True
        return False

    def get_path_id(self, path):
        """获取路径ID缓存"""
        return self.path_id_cache.get(path)

    def set_path_id(self, path, file_id):
        """设置路径ID缓存"""
        self.path_id_cache[path] = file_id
        # 异步保存到磁盘
        try:
            self.save_path_cache()
        except Exception:
            pass
    

    def clear_all_cache(self):
        """清除所有缓存"""
        old_direct = len(self.direct_link_cache)
        old_path = len(self.path_id_cache)
        self.direct_link_cache.clear()
        self.path_id_cache.clear()

        # 删除持久化的缓存文件
        try:
            if self.PATH_CACHE_FILE.exists():
                self.PATH_CACHE_FILE.unlink()
        except Exception as e:
            logger.warning(f"删除缓存文件失败: {e}")

        logger.info(f"缓存已清除: 直链={old_direct}, 路径={old_path}")

        return {
            'cleared': {
                'direct_links': old_direct,
                'path_ids': old_path
            }
        }

    def get_cache_stats(self):
        """获取缓存统计"""
        return {
            'direct_links': len(self.direct_link_cache),
            'path_ids': len(self.path_id_cache)
        }