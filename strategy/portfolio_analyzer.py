# -*- coding: utf-8 -*-
"""
[DEPRECATED] 组合策略分析模块已迁移到 strategy.portfolio
请使用 from strategy.portfolio import ... 导入
"""
import warnings
warnings.warn(
    "strategy.portfolio_analyzer 已废弃，所有功能已迁移到 strategy.portfolio，请更新导入路径",
    DeprecationWarning,
    stacklevel=2
)

# 转发导入，保持向下兼容
from .portfolio import (
    StrategyCorrelationAnalyzer,
    PortfolioBacktester,
    run_phase2_analysis
)

__all__ = [
    'StrategyCorrelationAnalyzer',
    'PortfolioBacktester',
    'run_phase2_analysis'
]
