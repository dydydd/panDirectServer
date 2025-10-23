#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import time
import random
import logging
from urllib.parse import urlparse, parse_qs, urlencode

logger = logging.getLogger(__name__)

class URLAuthManager:
    """123网盘 URL 鉴权管理器"""
    
    @staticmethod
    def add_auth_to_url(url, secret_key, uid, expire_seconds=3600):
        """
        为123网盘直链添加鉴权参数
        
        :param url: 原始直链 URL
        :param secret_key: 鉴权密钥（在123网盘后台配置）
        :param uid: 云盘UID
        :param expire_seconds: 过期时间（秒）
        :return: 带鉴权的URL
        
        算法说明：
        auth_key = $timestamp-$rand-$uid-$md5hash
        md5hash = md5(/$path-$timestamp-$rand-$uid-$secret_key)
        
        示例：
        原始URL: http://vip.123pan.cn/13/files/1.txt
        鉴权URL: http://vip.123pan.cn/13/files/1.txt?auth_key=1689220731-123-13-3bdacc0e031fd67fe829152f37c8fbad
        """
        try:
            # 解析URL
            from urllib.parse import unquote
            parsed = urlparse(url)
            
            # 获取路径并解码（签名必须使用原始未编码的路径）
            path = unquote(parsed.path)  # URL解码，例如: %E5%AA%92 -> 媒
            
            logger.debug(f"📍 URL路径: {parsed.path}")
            logger.debug(f"📍 解码路径: {path}")
            
            # 生成时间戳（过期时间）
            timestamp = int(time.time()) + expire_seconds
            
            # 生成随机数
            rand = random.randint(100, 999)
            
            # 构建待签名字符串
            # 格式：$path-$timestamp-$rand-$uid-$secret_key
            # 注意：路径必须是解码后的原始路径
            sign_string = f"{path}-{timestamp}-{rand}-{uid}-{secret_key}"
            
            logger.debug(f"🔐 签名字符串: {sign_string[:100]}...")
            
            # 计算MD5
            md5_hash = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
            
            # 构建auth_key
            # 格式：$timestamp-$rand-$uid-$md5hash
            auth_key = f"{timestamp}-{rand}-{uid}-{md5_hash}"
            
            # 添加到URL
            if '?' in url:
                auth_url = f"{url}&auth_key={auth_key}"
            else:
                auth_url = f"{url}?auth_key={auth_key}"
            
            logger.debug(f"✅ 鉴权URL生成成功")
            logger.debug(f"  auth_key: {auth_key}")
            logger.debug(f"  过期时间: {expire_seconds}秒后")
            
            return auth_url
            
        except Exception as e:
            logger.error(f"❌ 生成鉴权URL失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return url  # 失败时返回原URL
    
    @staticmethod
    def is_123pan_url(url, custom_domains=None):
        """
        判断是否是123网盘URL（需要添加鉴权）
        
        :param url: 要检查的URL
        :param custom_domains: 用户自定义的域名列表
        :return: True表示需要鉴权，False表示跳过
        """
        if not url:
            return False
        
        # 1. 检查官方域名
        official_domains = [
            'vip.123pan.cn',
            '123pan.cn',
            'cjjd19.com',
            'download-cdn.cjjd19.com'
        ]
        for domain in official_domains:
            if domain in url:
                logger.debug(f"  ✅ 匹配官方域名: {domain}")
                return True
        
        # 2. 检查用户配置的自定义域名
        if custom_domains and isinstance(custom_domains, list):
            for domain in custom_domains:
                if domain and domain in url:
                    logger.debug(f"  ✅ 匹配自定义域名: {domain}")
                    return True
        
        # 3. 不匹配任何规则，跳过鉴权
        logger.debug(f"  ⚪ URL不匹配，跳过鉴权")
        return False

