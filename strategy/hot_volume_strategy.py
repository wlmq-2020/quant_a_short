#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
热点成交量选股策略
选股逻辑：
1. 股票属于当前市场热点板块
2. 成交量最近保持平稳
3. 周线开始放量
4. 日线也开始放量
"""

import backtrader as bt
from typing import List

from strategy.strategy import BaseAStockStrategy
from data_fetcher.hot_plate_fetcher import hot_plate_fetcher
from logger import GlobalLogger


class HotVolumeStrategy(BaseAStockStrategy):
    """热点成交量选股策略"""

    params = (
        # 热点参数
        ('hot_period', 3),                # 最近N个交易日的热点
        ('hot_top_n', 10),                # 取TOP N热点板块
        ('hot_filter_enable', True),      # 是否启用热点过滤

        # 成交量平稳参数
        ('steady_period', 10),            # 最近P个交易日成交量平稳期
        ('steady_threshold', 0.3),        # 成交量波动率阈值（标准差/均值）

        # 周线放量参数
        ('week_ma_period', 20),           # 周线成交量均线周期
        ('week_volume_ratio', 1.5),       # 周线放量倍数
        ('week_vol_enable', True),        # 是否启用周线放量过滤

        # 日线放量参数
        ('day_ma_period', 10),            # 日线成交量均线周期
        ('day_volume_ratio', 2.0),        # 日线放量倍数
        ('day_vol_enable', True),         # 是否启用日线放量过滤

        # 交易参数（继承自基类，可以覆盖）
        ('stop_loss_ratio', 0.05),        # 止损比例
        ('take_profit_ratio', 0.15),      # 止盈比例
        ('position_ratio', 0.8),          # 仓位比例
        ('volume_filter', False),         # 关闭基类默认的成交量过滤，使用自定义的
    )

    def __init__(self):
        """初始化策略"""
        super().__init__()

        # 获取当前股票代码
        self.stock_code = self.datas[0]._name
        # 热点股票列表缓存（避免重复计算）
        self._hot_stocks_cache: List[str] = []
        self._cache_update_date = None
        self.logger = GlobalLogger.get_logger(__name__)

    def _add_indicators(self):
        """添加技术指标"""
        # 1. 日线成交量相关指标
        self.day_vol_sma = bt.indicators.SMA(
            self.datavolume,
            period=self.p.day_ma_period
        )
        self.day_vol_std = bt.indicators.StdDev(
            self.datavolume,
            period=self.p.steady_period
        )

        # 2. 周线数据重采样
        self.week_data = self.resampledata(
            self.datas[0],
            timeframe=bt.TimeFrame.Weeks,
            compression=1
        )
        # 周线成交量均线
        self.week_vol_sma = bt.indicators.SMA(
            self.week_data.volume,
            period=self.p.week_ma_period
        )

    def _is_hot_stock(self) -> bool:
        """检查当前股票是否属于热点板块（无未来数据泄露版）"""
        if not self.p.hot_filter_enable:
            return True

        # 每日更新一次缓存
        current_date = self.datas[0].datetime.date(0)
        if self._cache_update_date != current_date or not self._hot_stocks_cache:
            try:
                # 转换为YYYYMMDD格式，传入end_date参数，查询对应日期的历史热点，避免未来数据泄露
                end_date = current_date.strftime('%Y%m%d')
                self._hot_stocks_cache = hot_plate_fetcher.get_hot_stocks(
                    days=self.p.hot_period,
                    top_n=self.p.hot_top_n,
                    end_date=end_date
                )
            except Exception as e:
                self.logger.warning(f"获取热点股票列表失败，使用全市场股票池: {str(e)}")
                # 异常降级：热点获取失败时不过滤，使用全市场股票池
                return True
            self._cache_update_date = current_date

        # 统一股票代码格式，完全匹配避免错误
        # 当前股票代码去掉前缀
        current_stock = self.stock_code
        if current_stock.startswith('sh') or current_stock.startswith('sz'):
            current_stock = current_stock[2:]

        # 热点股票代码也去掉前缀，完全匹配
        for hot_stock in self._hot_stocks_cache:
            hot_stock_no_prefix = hot_stock[2:] if hot_stock.startswith(('sh', 'sz')) else hot_stock
            if hot_stock_no_prefix == current_stock:
                return True

        return False

    def _is_volume_steady(self) -> bool:
        """检查成交量是否平稳"""
        # 确保有足够的数据
        if len(self.datavolume) < self.p.steady_period:
            return False

        vol_mean = self.day_vol_sma[0]
        if vol_mean <= 0:
            return False

        # 波动率 = 标准差 / 均值
        volatility = self.day_vol_std[0] / vol_mean
        return volatility <= self.p.steady_threshold

    def _is_week_volume_surging(self) -> bool:
        """检查周线是否放量"""
        if not self.p.week_vol_enable:
            return True

        # 确保周线有足够的数据
        if len(self.week_vol_sma) < 2:
            return False

        # 最近1~2周成交量大于均线倍数
        current_week_vol = self.week_data.volume[0]
        prev_week_vol = self.week_data.volume[-1]
        week_ma = self.week_vol_sma[0]

        if week_ma <= 0:
            return False

        return (current_week_vol >= week_ma * self.p.week_volume_ratio) or \
               (prev_week_vol >= week_ma * self.p.week_volume_ratio)

    def _is_day_volume_surging(self) -> bool:
        """检查日线是否放量"""
        if not self.p.day_vol_enable:
            return True

        if len(self.day_vol_sma) < 2:
            return False

        # 最近1~2日成交量大于均线倍数
        current_vol = self.datavolume[0]
        prev_vol = self.datavolume[-1]
        day_ma = self.day_vol_sma[0]

        if day_ma <= 0:
            return False

        return (current_vol >= day_ma * self.p.day_volume_ratio) or \
               (prev_vol >= day_ma * self.p.day_volume_ratio)

    def next(self):
        """策略核心逻辑"""
        if self.order:
            return

        if not self.position:
            # 空仓状态：检查买入条件
            is_hot = self._is_hot_stock()
            is_steady = self._is_volume_steady()
            week_surging = self._is_week_volume_surging()
            day_surging = self._is_day_volume_surging()

            # 所有条件满足则买入
            if is_hot and is_steady and week_surging and day_surging:
                size = self.calculate_position_size()
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            # 持仓状态：检查卖出条件
            t1_ok = self.check_t1_rule()
            stop_loss = self.check_stop_loss()
            take_profit = self.check_take_profit()

            # 满足条件则卖出
            if t1_ok and (stop_loss or take_profit):
                self.order = self.sell(size=self.position.size)
