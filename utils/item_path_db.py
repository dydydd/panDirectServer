#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ItemPathDatabase:
    """
    Item ID 到文件路径的永久映射数据库
    用于跳过Emby API查询，直接获取文件路径
    """
    
    def __init__(self):
        self.db_file = Path('config/item_path_db.json')
        self.db = self._load_db()
    
    def _load_db(self):
        """加载数据库"""
        try:
            if self.db_file.exists():
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    db = json.load(f)
                    logger.info(f"✅ 已加载路径映射数据库: {len(db)} 条记录")
                    return db
            else:
                logger.info("📝 路径映射数据库不存在，创建新文件")
                return {}
        except Exception as e:
            logger.error(f"❌ 加载路径映射数据库失败: {e}")
            return {}
    
    def _save_db(self):
        """保存数据库"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
            
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.db, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"💾 已保存路径映射数据库: {len(self.db)} 条记录")
        except Exception as e:
            logger.error(f"❌ 保存路径映射数据库失败: {e}")
    
    def get(self, item_id):
        """
        获取item对应的文件路径
        
        :param item_id: Emby item ID
        :return: 文件路径或None
        """
        return self.db.get(str(item_id))
    
    def set(self, item_id, file_path):
        """
        设置item对应的文件路径
        
        :param item_id: Emby item ID
        :param file_path: 文件路径
        """
        self.db[str(item_id)] = file_path
        self._save_db()
        logger.debug(f"📝 记录映射: {item_id} → {file_path[:50]}...")
    
    def has(self, item_id):
        """检查是否存在映射"""
        return str(item_id) in self.db
    
    def remove(self, item_id):
        """删除映射"""
        if str(item_id) in self.db:
            del self.db[str(item_id)]
            self._save_db()
            logger.debug(f"🗑️ 删除映射: {item_id}")
    
    def clear(self):
        """清空数据库"""
        self.db = {}
        self._save_db()
        logger.info("🗑️ 已清空路径映射数据库")
    
    def stats(self):
        """获取统计信息"""
        return {
            'total': len(self.db),
            'size': os.path.getsize(self.db_file) if self.db_file.exists() else 0
        }

