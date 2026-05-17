# -*- coding: utf-8 -*-
"""
动态参数模块
处理最优参数的加载、缓存、校验等动态逻辑
"""
import json
from pathlib import Path
from typing import Dict, List


class ConfigParams:
    """动态参数类"""

    # ========== 最优参数缓存 ==========
    _best_params_cache = None
    _best_params_mtime = None

    @classmethod
    def _load_best_params(cls):
        """加载最优参数（内部使用）"""
        import logging
        logger = logging.getLogger(__name__)

        params_path = cls.get_best_params_path()
        if not params_path.exists():
            logger.debug(f"最优参数文件不存在：{params_path}，将使用默认参数")
            return {}

        mtime = params_path.stat().st_mtime
        if cls._best_params_cache is None or cls._best_params_mtime != mtime:
            try:
                with open(params_path, 'r', encoding='utf-8') as f:
                    cls._best_params_cache = json.load(f)
                cls._best_params_mtime = mtime
                logger.debug(f"已加载最优参数文件：{params_path}")
            except json.JSONDecodeError as e:
                logger.warning(f"最优参数文件JSON格式错误：{e}，文件可能已损坏，将使用默认参数")
                cls._best_params_cache = {}
            except Exception as e:
                logger.warning(f"加载最优参数文件失败：{e}，将使用默认参数")
                cls._best_params_cache = {}
        return cls._best_params_cache

    @classmethod
    def get_optimized_params(cls, strategy_type: str) -> Dict:
        """
        获取指定策略的最优参数

        参数:
            strategy_type: 策略类型

        返回:
            dict: 最优参数字典（仅best_params部分）
        """
        all_params = cls._load_best_params()
        strategy_data = all_params.get(strategy_type, {})
        return strategy_data.get('best_params', {})

    @classmethod
    def get_best_params(cls, strategy_type: str) -> Dict:
        """
        获取指定策略的最优参数（对外公开方法，避免直接调用私有方法）

        参数:
            strategy_type: 策略类型

        返回:
            dict: 最优参数字典（仅best_params部分）
        """
        return cls.get_optimized_params(strategy_type)

    @classmethod
    def get_all_optimized_strategies(cls) -> List[str]:
        """获取所有已优化的策略列表"""
        all_params = cls._load_best_params()
        return list(all_params.keys())

    @classmethod
    def get_best_params_path(cls) -> Path:
        """获取最优参数文件路径"""
        return cls.CONFIG_DIR / "best_strategy_params.json"
