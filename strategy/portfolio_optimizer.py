# -*- coding: utf-8 -*-
"""
[DEPRECATED] 组合策略优化模块已迁移到 strategy.portfolio
请使用 from strategy.portfolio import ... 导入
"""
import warnings
warnings.warn(
    "strategy.portfolio_optimizer 已废弃，所有功能已迁移到 strategy.portfolio，请更新导入路径",
    DeprecationWarning,
    stacklevel=2
)

# 转发导入，保持向下兼容
from .portfolio import (
    StrategyConfig,
    PortfolioStrategy,
    RealStrategyBacktester,
    PortfolioRotationTester,
    save_portfolio_results,
    create_balanced_portfolio,
    create_aggressive_portfolio,
    create_conservative_portfolio
)

__all__ = [
    'StrategyConfig',
    'PortfolioStrategy',
    'RealStrategyBacktester',
    'PortfolioRotationTester',
    'save_portfolio_results',
    'create_balanced_portfolio',
    'create_aggressive_portfolio',
    'create_conservative_portfolio'
]
