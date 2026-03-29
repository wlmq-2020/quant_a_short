# -*- coding: utf-8 -*-
"""
策略参数空间定义
定义所有策略的参数搜索范围
"""
from itertools import product


# 所有策略的参数空间定义（精简优化版本 - 平衡速度和效果）
PARAM_SPACES = {
    'macd_kdj': {
        'macd_fast': [8, 12, 16],
        'macd_slow': [20, 26, 32],
        'macd_signal': [6, 9, 12],
        'kdj_n': [6, 9, 14],
        'kdj_m1': [2, 3, 5],
        'kdj_m2': [2, 3, 5],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'rsi': {
        'rsi_period': [7, 14, 21],
        'rsi_overbought': [65, 70, 75],
        'rsi_oversold': [25, 30, 35],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'bollinger': {
        'bb_period': [15, 20, 25],
        'bb_std': [1.5, 2.0, 2.5],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'ma_cross': {
        'ma_fast': [3, 5, 8],
        'ma_slow': [15, 20, 25],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'kdj_oversold': {
        'kdj_n': [6, 9, 14],
        'kdj_m1': [2, 3, 5],
        'kdj_m2': [2, 3, 5],
        'oversold_threshold': [15, 20, 25],
        'overbought_threshold': [75, 80, 85],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'macd_zero_axis': {
        'macd_fast': [8, 12, 16],
        'macd_slow': [20, 26, 32],
        'macd_signal': [6, 9, 12],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'triple_screen': {
        'trend_period': [15, 20, 25],
        'stoch_period': [10, 14, 18],
        'oversold_threshold': [25, 30, 35],
        'overbought_threshold': [65, 70, 75],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'turtle_trading': {
        'entry_period': [15, 20, 25],
        'exit_period': [8, 10, 12],
        'atr_period': [15, 20, 25],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'momentum': {
        'momentum_period': [7, 10, 14],
        'momentum_threshold': [0.02, 0.03, 0.05],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'mean_reversion': {
        'ma_period': [15, 20, 25],
        'std_threshold': [1.2, 1.5, 1.8],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'donchian': {
        'donchian_period': [15, 20, 25],
        'exit_period': [8, 10, 12],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'williams_r': {
        'williams_period': [10, 14, 18],
        'oversold': [-85, -80, -75],
        'overbought': [-25, -20, -15],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'cci': {
        'cci_period': [15, 20, 25],
        'cci_oversold': [-120, -100, -80],
        'cci_overbought': [80, 100, 120],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'ema_cross': {
        'ema_fast': [8, 12, 16],
        'ema_slow': [20, 26, 32],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'volume_spread': {
        'ma_short': [3, 5, 8],
        'ma_long': [15, 20, 25],
        'volume_ma_period': [15, 20, 25],
        'volume_multiplier': [1.5, 2.0, 2.5],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'sar': {
        'sar_af': [0.015, 0.02, 0.025],
        'sar_max_af': [0.15, 0.2, 0.25],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
    'keltner': {
        'kc_period': [15, 20, 25],
        'kc_multiplier': [1.5, 2.0, 2.5],
        'stop_loss_ratio': [0.03, 0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15, 0.20],
    },
}


def get_param_space(strategy_type):
    """
    获取策略的参数空间

    参数:
        strategy_type: 策略类型

    返回:
        dict: 参数空间字典
    """
    return PARAM_SPACES.get(strategy_type, {})


def generate_param_combinations(param_space):
    """
    生成参数组合

    参数:
        param_space: 参数空间字典 {param_name: [values]}

    返回:
        list: 参数组合列表，每个元素是 {param_name: value}
    """
    if not param_space:
        return []

    keys = list(param_space.keys())
    values = list(param_space.values())

    combinations = []
    for combo in product(*values):
        param_dict = dict(zip(keys, combo))
        combinations.append(param_dict)

    return combinations


def get_all_strategy_types():
    """获取所有策略类型列表"""
    return list(PARAM_SPACES.keys())
