# -*- coding: utf-8 -*-
"""
全局配置模块
集中管理所有配置参数
"""
from pathlib import Path
from .settings import ConfigSettings
from .params import ConfigParams


class Config(ConfigSettings, ConfigParams):
    """全局配置类，继承静态配置和动态参数"""
    pass


# 保持向下兼容，原来的导入方式可以继续使用
__all__ = ['Config']
