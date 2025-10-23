#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import logging
from pathlib import Path
from database.database import get_db_manager

logger = logging.getLogger(__name__)

class CacheManager:
    """缓存管理器 - SQLite 优化版本"""

    def __init__(self):
        # 获取数据库管理器
        self.db = get_db_manager()
        
        # 兼容性：从旧的JSON文件迁移数据
        self.PATH_CACHE_FILE = Path('config/path_cache.json')
        self._migrate_from_json()

    def _migrate_from_json(self):
        """从旧的JSON文件迁移数据到SQLite"""
        try:
            if self.PATH_CACHE_FILE.exists():
                logger.info("🔄 发现旧的路径缓存文件，开始迁移到SQLite...")
                with open(self.PATH_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        migrated = 0
                        for path, file_id in data.items():
                            if self.db.set_path_id(str(path), str(file_id)):
                                migrated += 1
                        
                        logger.info(f"✅ 迁移完成: {migrated} 条路径缓存")
                        
                        # 备份并删除旧文件
                        backup_file = self.PATH_CACHE_FILE.with_suffix('.json.bak')
                        self.PATH_CACHE_FILE.rename(backup_file)
                        logger.info(f"📦 旧文件已备份为: {backup_file}")
        except Exception as e:
            logger.warning(f"⚠️ 迁移路径缓存失败: {e}")

    def get_direct_link(self, path):
        """获取缓存的直链"""
        cached = self.db.get_direct_link(path)
        if cached:
            return {
                'url': cached['url'],
                'expire': cached['expire_time']
            }
        return None

    def set_direct_link(self, path, url, expire_time=3600):
        """设置直链缓存"""
        success = self.db.set_direct_link(path, url, expire_time)
        if success:
            logger.debug(f"✅ 直链缓存已设置: {path}")
        return success

    def is_direct_link_valid(self, path):
        """检查直链缓存是否有效"""
        cached = self.db.get_direct_link(path)
        return cached is not None

    def get_path_id(self, path):
        """获取路径ID缓存"""
        return self.db.get_path_id(path)

    def set_path_id(self, path, file_id):
        """设置路径ID缓存"""
        success = self.db.set_path_id(path, file_id)
        if success:
            logger.debug(f"✅ 路径ID缓存已设置: {path} -> {file_id}")
        return success
    

    def clear_all_cache(self):
        """清除所有缓存"""
        result = self.db.clear_all_cache()
        
        # 清理过期直链缓存
        expired_count = self.db.clear_expired_direct_links()
        if expired_count > 0:
            logger.info(f"🧹 已清理 {expired_count} 条过期直链")
        
        logger.info(f"✅ 缓存已清除: {result}")
        return {'cleared': result}

    def get_cache_stats(self):
        """获取缓存统计"""
        stats = self.db.get_cache_stats()
        
        # 简化返回格式以兼容原有代码
        return {
            'direct_links': stats.get('direct_links', {}).get('valid_count', 0),
            'path_ids': stats.get('path_ids', {}).get('total_count', 0),
            'detailed_stats': stats  # 提供详细统计
        }