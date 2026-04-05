# -*- coding: utf-8 -*-
"""
市场状态识别模块
用于识别趋势市、震荡市、熊市等市场状态

v2.0 改进版：
1. 基于价格计算趋势强度（不是收益率）
2. 放宽均线排列判断条件
3. 多指标综合判断
4. 保持 API 兼容性
"""
import numpy as np
import pandas as pd
from typing import Tuple, List


class MarketStateDetector:
    """市场状态识别器"""
    
    # 市场状态定义
    STATE_TRENDING = 'trending'      # 趋势市
    STATE_RANGE_BOUND = 'range_bound' # 震荡市
    STATE_BEARISH = 'bearish'         # 熊市
    STATE_BULLISH = 'bullish'         # 牛市
    
    def __init__(self, lookback_period: int = 20):
        """
        初始化市场状态识别器
        
        参数:
            lookback_period: 回顾周期（交易日）
        """
        self.lookback_period = lookback_period
    
    def detect(self, prices: pd.Series) -> str:
        """
        检测市场状态
        
        参数:
            prices: 价格序列
            
        返回:
            市场状态字符串
        """
        if len(prices) < self.lookback_period:
            return self.STATE_RANGE_BOUND
        
        # ===== 1. 计算趋势强度（v2 改进版）=====
        trend_strength = self._calculate_trend_strength(prices)
        
        # ===== 2. 计算均线排列和方向（v2 改进版）=====
        ma_trend, ma_direction = self._calculate_ma_trend(prices)
        
        # ===== 3. 计算波动率（v2 改进版）=====
        volatility = self._calculate_volatility(prices)
        
        # ===== 4. 综合判断 =====
        # 强趋势 + 明确方向 = 牛/熊市
        if trend_strength > 30 and ma_trend:
            if ma_direction > 0:
                return self.STATE_BULLISH
            else:
                return self.STATE_BEARISH
        # 中等趋势 = 趋势市
        elif trend_strength > 15 or ma_trend:
            return self.STATE_TRENDING
        # 低波动 + 无趋势 = 震荡市
        elif trend_strength < 10 and volatility < 0.3:
            return self.STATE_RANGE_BOUND
        # 默认情况
        else:
            return self.STATE_TRENDING if ma_trend else self.STATE_RANGE_BOUND
    
    def _calculate_trend_strength(self, prices: pd.Series) -> float:
        """
        计算趋势强度（v2 改进版：基于价格）
        
        参数:
            prices: 价格序列
            
        返回:
            0-50，值越大趋势越强
        """
        if len(prices) < 20:
            return 20.0
        
        # 使用最近20天价格
        recent_prices = prices.tail(20).values
        x = np.arange(len(recent_prices))
        
        # 对价格做线性回归
        slope, intercept = np.polyfit(x, recent_prices, 1)
        
        # 计算R平方
        y_pred = slope * x + intercept
        ss_res = np.sum((recent_prices - y_pred) ** 2)
        ss_tot = np.sum((recent_prices - np.mean(recent_prices)) ** 2)
        
        if ss_tot == 0:
            r_squared = 0
        else:
            r_squared = 1 - (ss_res / ss_tot)
        
        # 将R平方映射到0-50
        trend_strength = abs(r_squared) * 50
        
        return float(trend_strength)
    
    def _calculate_ma_trend(self, prices: pd.Series) -> Tuple[bool, int]:
        """
        计算均线排列（v2 改进版：放宽判断条件）
        
        参数:
            prices: 价格序列
            
        返回:
            (是否有趋势, 方向: 1=上涨, -1=下跌, 0=震荡)
        """
        if len(prices) < 20:
            return False, 0
        
        # 计算均线
        ma5 = prices.rolling(5).mean().iloc[-1]
        ma20 = prices.rolling(20).mean().iloc[-1]
        ma60 = prices.rolling(60).mean().iloc[-1] if len(prices) >= 60 else ma20
        current = prices.iloc[-1]
        
        # ===== 方法1: 严格排列（用于强趋势判断）=====
        strict_bull = current > ma5 > ma20 > ma60
        strict_bear = current < ma5 < ma20 < ma60
        
        # ===== 方法2: 宽松排列（用于中等趋势判断）=====
        # 检查相对位置，允许1%误差
        def is_close(a, b, tol=0.01):
            return abs(a - b) / max(abs(a), abs(b), 1e-8) < tol
        
        loose_bull = (
            current >= ma5 * 0.99 and
            ma5 >= ma20 * 0.99 and
            ma20 >= ma60 * 0.99 and
            current > ma60
        )
        
        loose_bear = (
            current <= ma5 * 1.01 and
            ma5 <= ma20 * 1.01 and
            ma20 <= ma60 * 1.01 and
            current < ma60
        )
        
        # ===== 方法3: 基于均线方向 =====
        ma_trending_up = ma_trending_down = False
        if len(prices) >= 40:
            ma20_prev = prices.rolling(20).mean().iloc[-11]
            ma60_prev = prices.rolling(60).mean().iloc[-11] if len(prices)>=70 else ma20_prev
            
            ma_trending_up = ma20 > ma20_prev * 1.005 and ma60 > ma60_prev * 1.005
            ma_trending_down = ma20 < ma20_prev * 0.995 and ma60 < ma60_prev * 0.995
        
        # ===== 综合判断 =====
        has_trend = False
        direction = 0
        
        if strict_bull:
            has_trend = True
            direction = 1
        elif strict_bear:
            has_trend = True
            direction = -1
        elif loose_bull and ma_trending_up:
            has_trend = True
            direction = 1
        elif loose_bear and ma_trending_down:
            has_trend = True
            direction = -1
        elif ma_trending_up:
            has_trend = True
            direction = 1
        elif ma_trending_down:
            has_trend = True
            direction = -1
        
        return has_trend, direction
    
    def _calculate_volatility(self, prices: pd.Series) -> float:
        """
        计算波动率（v2 改进版：标准化到0-1范围）
        
        参数:
            prices: 价格序列
            
        返回:
            0-1 的标准化波动率
        """
        if len(prices) < 2:
            return 0.1
        
        returns = prices.pct_change().dropna()
        daily_vol = returns.std()
        normalized_vol = min(1.0, daily_vol * 10)
        
        return float(normalized_vol)
    
    def get_state_info(self, prices: pd.Series) -> dict:
        """
        获取详细的状态信息（保持兼容性）
        
        参数:
            prices: 价格序列
            
        返回:
            状态信息字典
        """
        state = self.detect(prices)
        
        return {
            'state': state,
            'adx': self._calculate_trend_strength(prices),  # 兼容旧版 API
            'trend_strength': self._calculate_trend_strength(prices),  # 新版字段
            'volatility': self._calculate_volatility(prices),
            'lookback_period': self.lookback_period
        }


# ========== 策略轮动器 ==========

class StrategyRotator:
    """策略轮动器"""
    
    def __init__(self, market_detector: MarketStateDetector = None):
        """
        初始化策略轮动器
        
        参数:
            market_detector: 市场状态识别器
        """
        self.market_detector = market_detector or MarketStateDetector()
        
        # 不同市场状态下的推荐策略
        self.state_strategies = {
            MarketStateDetector.STATE_BULLISH: ['ema_cross', 'sar', 'rsi'],
            MarketStateDetector.STATE_BEARISH: ['mean_reversion', 'cci', 'empty'],
            MarketStateDetector.STATE_TRENDING: ['turtle_trading', 'donchian', 'momentum'],
            MarketStateDetector.STATE_RANGE_BOUND: ['rsi', 'mean_reversion', 'bollinger'],
        }
    
    def get_recommended_strategies(self, prices: pd.Series) -> List[str]:
        """
        获取推荐策略列表
        
        参数:
            prices: 价格序列
            
        返回:
            推荐策略列表
        """
        state = self.market_detector.detect(prices)
        return self.state_strategies.get(state, ['rsi', 'mean_reversion'])
    
    def should_rotate(self, current_strategies: List[str], prices: pd.Series) -> bool:
        """
        判断是否需要轮动
        
        参数:
            current_strategies: 当前策略列表
            prices: 价格序列
            
        返回:
            是否需要轮动
        """
        recommended = self.get_recommended_strategies(prices)
        
        overlap = len(set(current_strategies) & set(recommended))
        total = len(set(current_strategies) | set(recommended))
        
        if total == 0:
            return True
        
        return overlap / total < 0.5


if __name__ == '__main__':
    print("="*80)
    print("市场状态识别模块 v2.0")
    print("="*80)
    print("\n改进点:")
    print("1. 基于价格计算趋势强度（不是收益率）")
    print("2. 放宽均线排列判断条件")
    print("3. 多指标综合判断")
    print("4. 保持 API 兼容性")
    print("\n使用示例:")
    print("  from strategy.market_state import MarketStateDetector, StrategyRotator")
    print("  detector = MarketStateDetector(lookback_period=20)")
    print("  state = detector.detect(price_series)")
    print("  info = detector.get_state_info(price_series)")
    print("  rotator = StrategyRotator(detector)")
    print("  strategies = rotator.get_recommended_strategies(price_series)")
    print("\n" + "="*80)
