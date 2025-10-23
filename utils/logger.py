#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

def setup_logger():
    """设置日志配置"""
    logging.basicConfig(
        level=logging.WARNING,  # 只显示WARNING及以上级别的日志
        format='%(asctime)s - %(levelname)s - %(message)s'  # 简化格式
    )
    
    # 为核心模块设置INFO级别
    core_loggers = [
        'utils.logger',
        'services.emby_proxy', 
        'services.pan123_service',
        'models.client'
    ]
    
    for logger_name in core_loggers:
        core_logger = logging.getLogger(logger_name)
        core_logger.setLevel(logging.INFO)
    
    return logging.getLogger(__name__)

def get_logger(name=None):
    """获取日志记录器"""
    return logging.getLogger(name or __name__)