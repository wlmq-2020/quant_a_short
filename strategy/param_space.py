# -*- coding: utf-8 -*-
"""
策略参数空间定义
定义所有策略的参数搜索范围
"""
from itertools import product


# 优化策略的参数空间定义（简化版 - 每个参数2个值，删除冗余参数）
OPTIMIZED_PARAM_SPACES = {
    'macd_kdj_fibonacci': {
        'macd_fast': [8, 12],
        'macd_slow': [21, 26],
        'macd_signal': [5, 8],
        'kdj_n': [6, 9],
        'kdj_m1': [2, 3],
        'kdj_m2': [2, 3],
        'stop_loss_ratio': [0.05, 0.08],
        'take_profit_ratio': [0.12, 0.20],
    },
    'boll_rsi_optimized': {
        'bb_period': [15, 20],
        'bb_std': [1.8, 2.2],
        'rsi_period': [14, 18],
        'rsi_overbought': [65, 70],
        'rsi_oversold': [30, 35],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    'kdj_rsi_optimized': {
        'kdj_n': [9, 14],
        'kdj_m1': [3, 5],
        'kdj_m2': [3, 5],
        'rsi_period': [14, 18],
        'rsi_overbought': [65, 70],
        'rsi_oversold': [30, 35],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    'macd_with_atr': {
        'macd_fast': [8, 12],
        'macd_slow': [20, 26],
        'macd_signal': [6, 9],
        'atr_period': [10, 14],
        'atr_multiplier': [1.5, 2.5],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    'rsi_with_trend': {
        'rsi_period': [10, 18],
        'rsi_overbought': [65, 75],
        'rsi_oversold': [25, 35],
        'ma_period': [15, 25],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    'turtle_with_filter': {
        'entry_period': [15, 20],
        'exit_period': [8, 12],
        'atr_period': [10, 14],
        'atr_multiplier': [1.5, 2.5],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    # 新增的13个策略参数空间（简化版）
    'ema_rsi': {
        'ema_short': [15, 20],
        'ema_long': [50, 60],
        'rsi_period': [12, 16],
        'rsi_overbought': [65, 75],
        'rsi_oversold': [25, 35],
        'stop_loss_ratio': [0.06, 0.10],
        'take_profit_ratio': [0.12, 0.18],
    },
    'dual_macd': {
        'macd_fast': [10, 12],
        'macd_slow': [24, 28],
        'macd_signal': [8, 10],
        'atr_period': [12, 16],
        'atr_trail_n': [2.0, 3.0],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    'macd': {
        'macd_fast': [10, 12],
        'macd_slow': [24, 28],
        'macd_signal': [8, 10],
        'stop_loss_ratio': [0.06, 0.10],
        'take_profit_ratio': [0.12, 0.18],
    },
    'boll_rsi': {
        'boll_period': [15, 20],
        'bb_std': [1.8, 2.2],
        'rsi_period': [12, 16],
        'rsi_oversold': [30, 40],
        'rsi_overbought': [65, 75],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    'turtle_breakout': {
        'entry_period': [15, 20],
        'exit_period': [8, 12],
        'atr_period': [10, 14],
        'atr_mult': [1.5, 2.5],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    'triple_ema': {
        'ema_short': [5, 10],
        'ema_mid': [20, 25],
        'ema_long': [50, 60],
        'stop_loss_ratio': [0.05, 0.09],
        'take_profit_ratio': [0.12, 0.18],
    },
    'kdj_macd_resonance': {
        'kdj_n': [7, 11],
        'kdj_m1': [2, 4],
        'kdj_m2': [2, 4],
        'macd_fast': [10, 14],
        'macd_slow': [24, 28],
        'macd_signal': [8, 10],
        'stop_loss_ratio': [0.05, 0.09],
        'take_profit_ratio': [0.15, 0.20],
    },
    'rsi_atr_adaptive': {
        'rsi_period': [12, 16],
        'rsi_oversold': [28, 32],
        'rsi_overbought': [68, 72],
        'atr_period': [12, 16],
        'atr_mult_normal': [2.5, 3.5],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    'macd_boll': {
        'macd_fast': [10, 14],
        'macd_slow': [24, 28],
        'macd_signal': [8, 10],
        'boll_period': [18, 22],
        'bb_std': [1.8, 2.2],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    'kdj_rsi': {
        'kdj_n': [7, 11],
        'kdj_m1': [2, 4],
        'kdj_m2': [2, 4],
        'rsi_period': [12, 16],
        'rsi_oversold': [28, 32],
        'rsi_overbought': [68, 72],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.12, 0.18],
    },
    'ma_volume': {
        'ma_short': [8, 12],
        'ma_long': [25, 35],
        'vol_period': [15, 25],
        'vol_mult': [1.3, 1.7],
        'stop_loss_ratio': [0.05, 0.07],
        'take_profit_ratio': [0.12, 0.18],
    },
    'atr_stop': {
        'breakout_period': [15, 25],
        'atr_period': [12, 16],
        'atr_multiplier': [1.8, 2.2],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
    'composite': {
        'ema_short': [18, 22],
        'ema_long': [55, 65],
        'macd_fast': [10, 14],
        'macd_slow': [24, 28],
        'macd_signal': [8, 10],
        'rsi_period': [12, 16],
        'stop_loss_ratio': [0.04, 0.06],
        'take_profit_ratio': [0.12, 0.18],
    },
}


# 所有策略的参数空间定义（快速优化版 - 每个参数2个值）
PARAM_SPACES = {
    'macd_kdj': {
        'macd_fast': [8, 12],
        'macd_slow': [20, 26],
        'macd_signal': [6, 9],
        'kdj_n': [6, 9],
        'kdj_m1': [2, 3],
        'kdj_m2': [2, 3],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.10, 0.15],
    },
    'rsi': {
        'rsi_period': [7, 14],
        'rsi_overbought': [65, 70],
        'rsi_oversold': [30, 35],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.15, 0.20],
    },
    'bollinger': {
        'bb_period': [15, 20],
        'bb_std': [2.0, 2.5],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.15, 0.20],
    },
    'ma_cross': {
        'ma_fast': [5, 8],
        'ma_slow': [20, 25],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.15, 0.20],
    },
    'kdj_oversold': {
        'kdj_n': [6, 9],
        'kdj_m1': [2, 3],
        'kdj_m2': [2, 3],
        'oversold_threshold': [20, 25],
        'overbought_threshold': [80, 85],
        'stop_loss_ratio': [0.05, 0.08],
        'take_profit_ratio': [0.12, 0.15],
    },
    'macd_zero_axis': {
        'macd_fast': [12, 16],
        'macd_slow': [20, 26],
        'macd_signal': [6, 9],
        'stop_loss_ratio': [0.05, 0.08],
        'take_profit_ratio': [0.15, 0.20],
    },
    'triple_screen': {
        'trend_period': [20, 25],
        'stoch_period': [14, 18],
        'oversold_threshold': [25, 30],
        'overbought_threshold': [65, 70],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.08, 0.12],
    },
    'turtle_trading': {
        'entry_period': [15, 20],
        'exit_period': [10, 12],
        'atr_period': [14, 20],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.12, 0.15],
    },
    'momentum': {
        'momentum_period': [7, 10],
        'momentum_threshold': [0.02, 0.03],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.15, 0.20],
    },
    'mean_reversion': {
        'ma_period': [15, 20],
        'std_threshold': [1.2, 1.5],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.15, 0.20],
    },
    'donchian': {
        'donchian_period': [15, 20],
        'exit_period': [10, 12],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.12, 0.15],
    },
    'williams_r': {
        'williams_period': [14, 18],
        'oversold': [-80, -85],
        'overbought': [-20, -25],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.15, 0.20],
    },
    'cci': {
        'cci_period': [15, 20],
        'cci_oversold': [-100, -120],
        'cci_overbought': [80, 100],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.15, 0.20],
    },
    'ema_cross': {
        'ema_fast': [8, 12],
        'ema_slow': [20, 26],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.12, 0.15],
    },
    'volume_spread': {
        'ma_short': [3, 5],
        'ma_long': [15, 20],
        'volume_ma_period': [15, 20],
        'volume_multiplier': [1.5, 2.0],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.15, 0.20],
    },
    'sar': {
        'sar_af': [0.015, 0.02],
        'sar_max_af': [0.15, 0.2],
        'stop_loss_ratio': [0.03, 0.05],
        'take_profit_ratio': [0.15, 0.20],
    },
    'keltner': {
        'kc_period': [15, 20],
        'kc_multiplier': [2.0, 2.5],
        'stop_loss_ratio': [0.05, 0.08],
        'take_profit_ratio': [0.10, 0.15],
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


def get_optimized_param_space(strategy_type):
    """
    获取优化策略的参数空间

    参数:
        strategy_type: 优化策略类型

    返回:
        dict: 参数空间字典
    """
    return OPTIMIZED_PARAM_SPACES.get(strategy_type, {})


def get_all_optimized_strategy_types():
    """获取所有优化策略类型列表"""
    return list(OPTIMIZED_PARAM_SPACES.keys())


def get_all_param_spaces():
    """获取所有参数空间（普通策略+优化策略）"""
    all_spaces = {}
    all_spaces.update(PARAM_SPACES)
    all_spaces.update(OPTIMIZED_PARAM_SPACES)
    return all_spaces


def get_all_strategy_types_including_optimized():
    """获取所有策略类型列表（包括优化策略）"""
    return list(get_all_param_spaces().keys())
