#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
from pathlib import Path
from database.database import get_db_manager

logger = logging.getLogger(__name__)

class ItemPathDatabase:
    """
    Item ID 到文件路径的永久映射数据库 - SQLite 优化版本
    用于跳过Emby API查询，直接获取文件路径，极大提升性能
    """
    
    def __init__(self):
        self.db_file = Path('config/item_path_db.json')
        self.db = get_db_manager()
        
        # 从旧JSON文件迁移数据
        self._migrate_from_json()
    
    def _migrate_from_json(self):
        """从旧JSON文件迁移数据到SQLite"""
        try:
            if self.db_file.exists():
                logger.info("🔄 发现旧的路径映射数据库，开始迁移到SQLite...")
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        migrated = 0
                        for item_id, file_path in data.items():
                            if self.db.set_item_path(str(item_id), str(file_path)):
                                migrated += 1
                        
                        logger.info(f"✅ 路径映射迁移完成: {migrated} 条记录")
                        
                        # 备份并删除旧文件
                        backup_file = self.db_file.with_suffix('.json.bak')
                        self.db_file.rename(backup_file)
                        logger.info(f"📦 旧数据库已备份为: {backup_file}")
        except Exception as e:
            logger.warning(f"⚠️ 迁移路径映射数据库失败: {e}")
    
    def get(self, item_id):
        """
        获取item对应的文件路径（SQLite优化版本）
        
        :param item_id: Emby item ID
        :return: 文件路径或None
        """
        file_path = self.db.get_item_path(str(item_id))
        if file_path:
            logger.debug(f"🎯 路径映射命中: {item_id} → {file_path[:50]}...")
        return file_path
    
    def set(self, item_id, file_path):
        """
        设置item对应的文件路径（SQLite优化版本）
        
        :param item_id: Emby item ID
        :param file_path: 文件路径
        """
        success = self.db.set_item_path(str(item_id), str(file_path))
        if success:
            logger.debug(f"📝 路径映射已记录: {item_id} → {file_path[:50]}...")
        return success
    
    def has(self, item_id):
        """检查是否存在映射（SQLite优化版本）"""
        return self.db.has_item_path(str(item_id))
    
    def remove(self, item_id):
        """删除映射（SQLite优化版本）"""
        success = self.db.remove_item_path(str(item_id))
        if success:
            logger.debug(f"🗑️ 删除映射: {item_id}")
        return success
    
    def clear(self):
        """清空数据库（危险操作，慎用）"""
        logger.warning("⚠️ 正在清空路径映射数据库...")
        # 实际上我们不提供清空功能，这些是永久数据
        logger.warning("⚠️ 为了数据安全，路径映射数据库不支持清空操作")
        return False
    
    def stats(self):
        """获取统计信息（SQLite优化版本）"""
        return self.db.get_item_path_stats()

