#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from database.config_manager_v2 import StandardConfigManager

# 使用标准SQLite配置管理器
class ConfigManager(StandardConfigManager):
    """配置管理器 - 纯SQLite存储版本"""
    
    def __init__(self):
        super().__init__()
        # 完全移除JSON依赖，纯SQLite存储