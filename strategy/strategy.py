# -*- coding: utf-8 -*-
"""
A股短线策略模块 - Backtrader版本（完整版）
提供多种A股高胜率短线策略 - 共36个策略

策略列表（共36个）:
【基础策略 - 17个】（历史分类，不再区分）
1. macd_kdj              - MACD+KDJ共振策略
2. rsi                   - RSI超买超卖策略
3. bollinger             - 布林带策略
4. ma_cross              - 均线交叉策略
5. kdj_oversold          - KDJ超卖超买策略
6. macd_zero_axis        - MACD零轴策略
7. triple_screen         - 三重滤网交易系统
8. turtle_trading        - 海龟交易策略
9. momentum              - 动量策略
10. mean_reversion       - 均值回归策略
11. donchian             - 唐奇安通道策略
12. williams_r           - 威廉指标策略
13. cci                  - 顺势指标策略
14. ema_cross            - 指数均线交叉策略
15. volume_spread        - 量价配合策略
16. sar                  - 抛物线转向指标策略
17. keltner              - 凯特纳通道策略

【优化策略 - 19个】（历史分类，不再区分）
18. macd_kdj_fibonacci  - MACD+KDJ共振策略（斐波那契参数优化版）
19. boll_rsi_optimized   - 布林带+RSI策略优化版
20. kdj_rsi_optimized    - KDJ+RSI策略优化版
21. macd_with_atr        - MACD策略优化版（加入ATR止损）
22. rsi_with_trend       - RSI策略优化版（加入趋势过滤）
23. turtle_with_filter   - 海龟策略优化版（加入波动率过滤）
24. ema_rsi              - 双EMA+RSI过滤策略
25. dual_macd            - 双线确认MACD策略 v5
26. macd                 - 基础MACD策略
27. boll_rsi             - 布林带+RSI均值回归策略
28. turtle_breakout      - 海龟突破策略（唐奇安通道）
29. triple_ema           - 三重EMA趋势+量价共振策略
30. kdj_macd_resonance   - KDJ+MACD双指标共振策略
31. rsi_atr_adaptive     - RSI超卖反弹+自适应ATR追踪止损
32. macd_boll            - MACD+布林带组合策略
33. kdj_rsi              - KDJ+RSI超买超卖策略
34. ma_volume            - 均线交叉+成交量确认策略
35. atr_stop             - ATR波动率止损策略
36. composite            - 综合多因子策略
"""
import pandas as pd
import numpy as np
import backtrader as bt


class BaseAStockStrategy(bt.Strategy):
    """
    A股策略基类
    提供通用功能和配置
    """
    params = (
        ('initial_capital', 100000.0),  # 初始资金
        ('position_ratio', 0.8),        # 仓位比例
        ('stop_loss_ratio', 0.05),      # 止损比例
        ('take_profit_ratio', 0.15),    # 止盈比例
        ('commission_rate', 0.00025),   # 手续费率
        ('stamp_duty_rate', 0.001),     # 印花税率
        ('transfer_fee_rate', 0.00002), # 过户费率
        ('min_commission', 5.0),        # 最低手续费
        ('t1_rule', True),              # T+1规则
        ('volume_filter', True),        # 成交量过滤
        ('volume_ratio', 1.5),          # 成交量倍数
    )

    def __init__(self):
        """初始化策略"""
        # 保存数据引用
        self.dataclose = self.datas[0].close
        self.dataopen = self.datas[0].open
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        self.datavolume = self.datas[0].volume

        # 订单跟踪
        self.order = None
        self.buyprice = None
        self.buycomm = None

        # 持仓状态
        self.position_entry_price = 0
        self.position_entry_date = None

        # 添加技术指标
        self._add_indicators()

    def _add_indicators(self):
        """添加技术指标 - 由子类实现"""
        pass

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.position_entry_price = order.executed.price
                self.position_entry_date = self.datas[0].datetime.date(0)
            elif order.issell():
                self.position_entry_price = 0
                self.position_entry_date = None

        self.order = None

    def notify_trade(self, trade):
        """交易通知"""
        if not trade.isclosed:
            return

    def next(self):
        """策略逻辑 - 由子类实现"""
        pass

    def stop(self):
        """策略结束"""
        pass

    def calculate_position_size(self):
        """
        计算买入仓位大小（通用方法）

        返回:
            int: 买入数量
        """
        cash = self.broker.getcash()
        position_value = cash * self.p.position_ratio
        size = int(position_value // self.dataclose[0])
        return size if size > 0 else 0

    def check_t1_rule(self):
        """
        检查T+1规则是否满足（通用方法）

        返回:
            bool: True表示可以卖出
        """
        if not self.p.t1_rule:
            return True
        if not self.position_entry_date:
            return False
        days_held = (self.datas[0].datetime.date(0) - self.position_entry_date).days
        return days_held >= 1

    def calculate_profit_pct(self):
        """
        计算当前持仓收益率（通用方法）

        返回:
            float: 收益率百分比
        """
        if not self.position_entry_price or self.position_entry_price <= 0:
            return 0.0
        current_price = self.dataclose[0]
        return (current_price - self.position_entry_price) / self.position_entry_price

    def check_stop_loss(self):
        """
        检查是否触发止损（通用方法）

        返回:
            bool: True表示触发止损
        """
        profit_pct = self.calculate_profit_pct()
        return profit_pct <= -self.p.stop_loss_ratio

    def check_take_profit(self):
        """
        检查是否触发止盈（通用方法）

        返回:
            bool: True表示触发止盈
        """
        profit_pct = self.calculate_profit_pct()
        return profit_pct >= self.p.take_profit_ratio

    def check_volume_filter(self, volume_ma=None):
        """
        检查成交量过滤条件（通用方法）

        参数:
            volume_ma: 成交量均线值，None则使用默认10日均线

        返回:
            bool: True表示成交量满足条件
        """
        if not self.p.volume_filter:
            return True
        if volume_ma is None:
            # 如果没有提供均线，使用默认10日均线
            if not hasattr(self, 'volume_ma10'):
                from backtrader.indicators import SimpleMovingAverage
                self.volume_ma10 = SimpleMovingAverage(self.datavolume, period=10)
            volume_ma = self.volume_ma10[0]
        return self.datavolume[0] >= volume_ma * self.p.volume_ratio


# ============================================================================
# 策略 - 36个
# ============================================================================

class MacdKdjStrategy(BaseAStockStrategy):
    """MACD+KDJ共振策略"""
    params = (
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('kdj_n', 9),
        ('kdj_m1', 3),
        ('kdj_m2', 3),
    )

    def _add_indicators(self):
        self.macd = bt.indicators.MACD(
            self.dataclose,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.stochastic = bt.indicators.Stochastic(
            self.data,
            period=self.p.kdj_n,
            period_dfast=self.p.kdj_m1,
            period_dslow=self.p.kdj_m2
        )
        self.k = self.stochastic.percK
        self.d = self.stochastic.percD
        self.j = 3 * self.k - 2 * self.d
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            macd_cross_up = (self.macd.macd[0] > self.macd.signal[0] and
                            self.macd.macd[-1] <= self.macd.signal[-1])
            kdj_cross_up = (self.k[0] > self.d[0] and
                           self.k[-1] <= self.d[-1] and self.k[0] < 50)
            kdj_macd_up = (self.k[0] > self.d[0] and
                          self.k[-1] <= self.d[-1] and self.macd.macd[0] > 0)
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if (macd_cross_up and (kdj_cross_up or kdj_macd_up) and volume_ok):
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            macd_cross_down = (self.macd.macd[0] < self.macd.signal[0] and
                              self.macd.macd[-1] >= self.macd.signal[-1])
            kdj_cross_down = (self.k[0] < self.d[0] and
                             self.k[-1] >= self.d[-1] and self.k[0] > 50)
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((macd_cross_down or kdj_cross_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class RsiStrategy(BaseAStockStrategy):
    """RSI超买超卖策略"""
    params = (
        ('rsi_period', 14),
        ('rsi_overbought', 70),
        ('rsi_oversold', 30),
    )

    def _add_indicators(self):
        self.rsi = bt.indicators.RSI(self.dataclose, period=self.p.rsi_period)
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            rsi_rebound = (self.rsi[0] > self.rsi[-1] and
                          self.rsi[-1] < self.p.rsi_oversold)
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if rsi_rebound and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            rsi_falling = (self.rsi[0] < self.rsi[-1] and
                          self.rsi[-1] > self.p.rsi_overbought)
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((rsi_falling or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class BollingerStrategy(BaseAStockStrategy):
    """布林带策略"""
    params = (
        ('bb_period', 20),
        ('bb_std', 2),
    )

    def _add_indicators(self):
        self.bollinger = bt.indicators.BollingerBands(
            self.dataclose,
            period=self.p.bb_period,
            devfactor=self.p.bb_std
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            below_lower = self.dataclose[-1] < self.bollinger.lines.bot[-1]
            cross_up = (self.dataclose[0] > self.bollinger.lines.bot[0] and
                       self.dataclose[-1] <= self.bollinger.lines.bot[-1])
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if below_lower and cross_up and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            above_upper = self.dataclose[-1] > self.bollinger.lines.top[-1]
            cross_down = (self.dataclose[0] < self.bollinger.lines.top[0] and
                         self.dataclose[-1] >= self.bollinger.lines.top[-1])
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((above_upper or cross_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class MaCrossStrategy(BaseAStockStrategy):
    """均线交叉策略"""
    params = (
        ('ma_fast', 5),
        ('ma_slow', 20),
    )

    def _add_indicators(self):
        self.ma_fast = bt.indicators.SimpleMovingAverage(
            self.dataclose, period=self.p.ma_fast
        )
        self.ma_slow = bt.indicators.SimpleMovingAverage(
            self.dataclose, period=self.p.ma_slow
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            ma_cross_up = (self.ma_fast[0] > self.ma_slow[0] and
                          self.ma_fast[-1] <= self.ma_slow[-1])
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if ma_cross_up and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            ma_cross_down = (self.ma_fast[0] < self.ma_slow[0] and
                            self.ma_fast[-1] >= self.ma_slow[-1])
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((ma_cross_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class KdjOversoldStrategy(BaseAStockStrategy):
    """KDJ超卖超买策略"""
    params = (
        ('kdj_n', 9),
        ('kdj_m1', 3),
        ('kdj_m2', 3),
        ('oversold_threshold', 20),
        ('overbought_threshold', 80),
    )

    def _add_indicators(self):
        self.stochastic = bt.indicators.Stochastic(
            self.data,
            period=self.p.kdj_n,
            period_dfast=self.p.kdj_m1,
            period_dslow=self.p.kdj_m2
        )
        self.k = self.stochastic.percK
        self.d = self.stochastic.percD
        self.j = 3 * self.k - 2 * self.d
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            k_oversold = self.k[0] < self.p.oversold_threshold
            kdj_cross_up = (self.k[0] > self.d[0] and
                           self.k[-1] <= self.d[-1])
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if k_oversold and kdj_cross_up and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            k_overbought = self.k[0] > self.p.overbought_threshold
            kdj_cross_down = (self.k[0] < self.d[0] and
                             self.k[-1] >= self.d[-1])
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((k_overbought or kdj_cross_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class MacdZeroAxisStrategy(BaseAStockStrategy):
    """MACD零轴策略"""
    params = (
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
    )

    def _add_indicators(self):
        self.macd = bt.indicators.MACD(
            self.dataclose,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            macd_below_zero = self.macd.macd[0] < 0
            macd_cross_up = (self.macd.macd[0] > self.macd.signal[0] and
                            self.macd.macd[-1] <= self.macd.signal[-1])
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if macd_below_zero and macd_cross_up and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            macd_above_zero = self.macd.macd[0] > 0
            macd_cross_down = (self.macd.macd[0] < self.macd.signal[0] and
                              self.macd.macd[-1] >= self.macd.signal[-1])
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((macd_above_zero and macd_cross_down) or stop_loss or take_profit) and t1_ok:
                self.order = self.sell(size=self.position.size)


class TripleScreenStrategy(BaseAStockStrategy):
    """三重滤网交易系统"""
    params = (
        ('trend_period', 20),
        ('stoch_period', 14),
        ('oversold_threshold', 30),
        ('overbought_threshold', 70),
    )

    def _add_indicators(self):
        self.trend_ema = bt.indicators.ExponentialMovingAverage(
            self.dataclose, period=self.p.trend_period
        )
        self.stochastic = bt.indicators.Stochastic(
            self.data, period=self.p.stoch_period
        )
        self.k = self.stochastic.percD
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        trend_up = self.trend_ema[0] > self.trend_ema[-5]

        if not self.position:
            k_oversold = self.k[0] < self.p.oversold_threshold
            price_up = self.dataclose[0] > self.dataclose[-1]
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if trend_up and k_oversold and price_up and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            k_overbought = self.k[0] > self.p.overbought_threshold
            price_down = self.dataclose[0] < self.dataclose[-1]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((not trend_up or k_overbought or price_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class TurtleTradingStrategy(BaseAStockStrategy):
    """海龟交易策略"""
    params = (
        ('entry_period', 20),
        ('exit_period', 10),
        ('atr_period', 20),
    )

    def _add_indicators(self):
        self.entry_high = bt.indicators.Highest(
            self.datahigh, period=self.p.entry_period
        )
        self.entry_low = bt.indicators.Lowest(
            self.datalow, period=self.p.exit_period
        )
        self.exit_high = bt.indicators.Highest(
            self.datahigh, period=self.p.exit_period
        )
        self.exit_low = bt.indicators.Lowest(
            self.datalow, period=self.p.exit_period
        )
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            break_up = self.dataclose[0] > self.entry_high[-1]
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if break_up and volume_ok:
                cash = self.broker.getcash()
                risk_per_trade = cash * 0.01
                atr_value = self.atr[0]
                if atr_value > 0:
                    position_value = risk_per_trade / (atr_value / self.dataclose[0])
                    position_value = min(position_value, cash * self.p.position_ratio)
                    size = position_value // self.dataclose[0]
                    if size > 0:
                        self.order = self.buy(size=size)
        else:
            break_down = self.dataclose[0] < self.exit_low[-1]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((break_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class MomentumStrategy(BaseAStockStrategy):
    """动量策略 - 追涨杀跌"""
    params = (
        ('momentum_period', 10),
        ('momentum_threshold', 0.03),
    )

    def _add_indicators(self):
        self.roc = bt.indicators.RateOfChange(
            self.dataclose, period=self.p.momentum_period
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            momentum_up = self.roc[0] > self.p.momentum_threshold
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if momentum_up and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            momentum_down = self.roc[0] < -self.p.momentum_threshold
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((momentum_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class MeanReversionStrategy(BaseAStockStrategy):
    """均值回归策略 - 跌破均值买入，突破均值卖出"""
    params = (
        ('ma_period', 20),
        ('std_threshold', 1.5),
    )

    def _add_indicators(self):
        self.ma = bt.indicators.SimpleMovingAverage(
            self.dataclose, period=self.p.ma_period
        )
        self.std = bt.indicators.StandardDeviation(
            self.dataclose, period=self.p.ma_period
        )
        self.upper_band = self.ma + self.std * self.p.std_threshold
        self.lower_band = self.ma - self.std * self.p.std_threshold
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            below_lower = self.dataclose[0] < self.lower_band[0]
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if below_lower and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            above_upper = self.dataclose[0] > self.upper_band[0]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((above_upper or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class DonchianStrategy(BaseAStockStrategy):
    """唐奇安通道突破策略"""
    params = (
        ('donchian_period', 20),
        ('exit_period', 10),
    )

    def _add_indicators(self):
        self.donchian_high = bt.indicators.Highest(
            self.datahigh, period=self.p.donchian_period
        )
        self.donchian_low = bt.indicators.Lowest(
            self.datalow, period=self.p.donchian_period
        )
        self.exit_low = bt.indicators.Lowest(
            self.datalow, period=self.p.exit_period
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            break_up = self.dataclose[0] > self.donchian_high[-1]
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if break_up and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            break_down = self.dataclose[0] < self.exit_low[-1]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((break_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class WilliamsRStrategy(BaseAStockStrategy):
    """威廉指标策略"""
    params = (
        ('williams_period', 14),
        ('oversold', -80),
        ('overbought', -20),
    )

    def _add_indicators(self):
        self.williams_r = bt.indicators.WilliamsR(
            self.data, period=self.p.williams_period
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            cross_oversold = (self.williams_r[0] > self.p.oversold and
                            self.williams_r[-1] <= self.p.oversold)
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if cross_oversold and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            cross_overbought = (self.williams_r[0] < self.p.overbought and
                              self.williams_r[-1] >= self.p.overbought)
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((cross_overbought or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class CCIStrategy(BaseAStockStrategy):
    """顺势指标策略"""
    params = (
        ('cci_period', 20),
        ('cci_oversold', -100),
        ('cci_overbought', 100),
    )

    def _add_indicators(self):
        self.cci = bt.indicators.CommodityChannelIndex(
            self.data, period=self.p.cci_period
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            cci_cross_up = (self.cci[0] > self.p.cci_oversold and
                          self.cci[-1] <= self.p.cci_oversold)
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if cci_cross_up and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            cci_cross_down = (self.cci[0] < self.p.cci_overbought and
                            self.cci[-1] >= self.p.cci_overbought)
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((cci_cross_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class EMACrossStrategy(BaseAStockStrategy):
    """指数均线交叉策略"""
    params = (
        ('ema_fast', 12),
        ('ema_slow', 26),
    )

    def _add_indicators(self):
        self.ema_fast = bt.indicators.ExponentialMovingAverage(
            self.dataclose, period=self.p.ema_fast
        )
        self.ema_slow = bt.indicators.ExponentialMovingAverage(
            self.dataclose, period=self.p.ema_slow
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            ema_cross_up = (self.ema_fast[0] > self.ema_slow[0] and
                          self.ema_fast[-1] <= self.ema_slow[-1])
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if ema_cross_up and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            ema_cross_down = (self.ema_fast[0] < self.ema_slow[0] and
                            self.ema_fast[-1] >= self.ema_slow[-1])
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((ema_cross_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class VolumeSpreadStrategy(BaseAStockStrategy):
    """量价配合策略"""
    params = (
        ('ma_short', 5),
        ('ma_long', 20),
        ('volume_ma_period', 20),
        ('volume_multiplier', 2.0),
    )

    def _add_indicators(self):
        self.ma_short = bt.indicators.SimpleMovingAverage(
            self.dataclose, period=self.p.ma_short
        )
        self.ma_long = bt.indicators.SimpleMovingAverage(
            self.dataclose, period=self.p.ma_long
        )
        self.volume_ma = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=self.p.volume_ma_period
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            ma_trend_up = self.ma_short[0] > self.ma_long[0]
            volume_surge = self.datavolume[0] > self.volume_ma[0] * self.p.volume_multiplier
            price_rise = self.dataclose[0] > self.dataclose[-1]

            if ma_trend_up and volume_surge and price_rise:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            ma_trend_down = self.ma_short[0] < self.ma_long[0]
            volume_drop = self.datavolume[0] > self.volume_ma[0] * 1.5
            price_fall = self.dataclose[0] < self.dataclose[-1]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((ma_trend_down or (volume_drop and price_fall) or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class SARStrategy(BaseAStockStrategy):
    """抛物线转向指标策略"""
    params = (
        ('sar_af', 0.02),
        ('sar_max_af', 0.2),
    )

    def _add_indicators(self):
        self.sar = bt.indicators.ParabolicSAR(
            self.data, af=self.p.sar_af, afmax=self.p.sar_max_af
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            sar_buy = self.dataclose[0] > self.sar[0] and self.dataclose[-1] <= self.sar[-1]
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if sar_buy and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            sar_sell = self.dataclose[0] < self.sar[0] and self.dataclose[-1] >= self.sar[-1]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((sar_sell or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class KeltnerChannelStrategy(BaseAStockStrategy):
    """凯特纳通道策略"""
    params = (
        ('kc_period', 20),
        ('kc_multiplier', 2.0),
    )

    def _add_indicators(self):
        self.ema = bt.indicators.ExponentialMovingAverage(
            self.dataclose, period=self.p.kc_period
        )
        self.atr = bt.indicators.ATR(self.data, period=self.p.kc_period)
        self.kc_upper = self.ema + self.atr * self.p.kc_multiplier
        self.kc_lower = self.ema - self.atr * self.p.kc_multiplier
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            breakout_up = self.dataclose[0] > self.kc_upper[0]
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if breakout_up and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            breakout_down = self.dataclose[0] < self.kc_lower[0]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((breakout_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class EmaRsiStrategy(BaseAStockStrategy):
    """双EMA+RSI过滤策略（简化版，易触发交易）"""
    params = (
        ('ema_short', 20),
        ('ema_long', 60),
        ('rsi_period', 14),
        ('rsi_overbought', 70),
        ('rsi_oversold', 30),
        ('stop_loss_ratio', 0.08),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.8),
    )

    def _add_indicators(self):
        self.ema_short = bt.indicators.EMA(self.dataclose, period=self.p.ema_short)
        self.ema_long = bt.indicators.EMA(self.dataclose, period=self.p.ema_long)
        self.rsi = bt.indicators.RSI(self.dataclose, period=self.p.rsi_period)
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            ema_gold_cross = (self.ema_short[0] > self.ema_long[0] and
                            self.ema_short[-1] <= self.ema_long[-1])
            rsi_filter = self.rsi[0] < self.p.rsi_overbought
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if ema_gold_cross and rsi_filter and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            ema_death_cross = (self.ema_short[0] < self.ema_long[0] and
                             self.ema_short[-1] >= self.ema_long[-1])
            rsi_overbought = self.rsi[0] >= self.p.rsi_overbought
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((ema_death_cross or rsi_overbought or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class DualMacdStrategy(BaseAStockStrategy):
    """
    双线确认MACD策略 v5

    核心逻辑：
      入场: MACD(12,26,9) 金叉 + MACD(5,13,6) 快线已在信号线上方（短期趋势确认）
      离场: MACD(12,26,9) 死叉 OR 自适应ATR追踪止损（随利润增长收紧）
      仓位: 每次满仓85%
    """
    params = (
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('conf_fast', 5),
        ('conf_slow', 13),
        ('conf_signal', 6),
        ('atr_period', 14),
        ('atr_trail_n', 2.5),
        ('atr_trail_hi', 1.8),
        ('atr_trail_pk', 1.2),
        ('profit_mid', 0.12),
        ('profit_pk', 0.30),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        # 慢速 MACD（主信号）
        self.macd = bt.indicators.MACD(
            self.dataclose,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        # 快速 MACD（确认信号）
        self.conf_macd = bt.indicators.MACD(
            self.dataclose,
            period_me1=self.p.conf_fast,
            period_me2=self.p.conf_slow,
            period_signal=self.p.conf_signal
        )
        # ATR（自适应止损）
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )
        self.trail_stop = 0

    def notify_order(self, order):
        super().notify_order(order)
        if order.isbuy() and order.status == order.Completed:
            self.trail_stop = self.dataclose[0] - self.atr[0] * self.p.atr_trail_n

    def next(self):
        if self.order:
            return

        if not self.position:
            # 入场条件
            macd_cross_up = (self.macd.macd[0] > self.macd.signal[0] and
                           self.macd.macd[-1] <= self.macd.signal[-1])
            if not macd_cross_up:
                return

            if self.conf_macd.macd[0] <= self.conf_macd.signal[0]:
                return

            if self.atr[0] <= 0:
                return

            cash = self.broker.getcash()
            position_value = cash * self.p.position_ratio
            size = position_value // self.dataclose[0]
            if size > 0:
                self.order = self.buy(size=size)
        else:
            if self.trail_stop > 0 and self.position_entry_price:
                pnl_pct = (self.dataclose[0] - self.position_entry_price) / self.position_entry_price

                if pnl_pct > self.p.profit_pk:
                    mult = self.p.atr_trail_pk
                elif pnl_pct > self.p.profit_mid:
                    mult = self.p.atr_trail_hi
                else:
                    mult = self.p.atr_trail_n

                new_stop = self.dataclose[0] - self.atr[0] * mult
                if new_stop > self.trail_stop:
                    self.trail_stop = new_stop

            macd_cross_dn = (self.macd.macd[0] < self.macd.signal[0] and
                           self.macd.macd[-1] >= self.macd.signal[-1])
            hit_stop = self.dataclose[0] <= self.trail_stop if self.trail_stop > 0 else False
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio or hit_stop
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((macd_cross_dn or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)
                self.trail_stop = 0


class MacdStrategy(BaseAStockStrategy):
    """MACD金叉死叉策略（带止损止盈、仓位控制）"""
    params = (
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('stop_loss_ratio', 0.08),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.8),
    )

    def _add_indicators(self):
        self.macd = bt.indicators.MACD(
            self.dataclose,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            macd_gold_cross = (self.macd.macd[0] > self.macd.signal[0] and
                            self.macd.macd[-1] <= self.macd.signal[-1])
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if macd_gold_cross and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            macd_death_cross = (self.macd.macd[0] < self.macd.signal[0] and
                            self.macd.macd[-1] >= self.macd.signal[-1])
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((macd_death_cross or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class BollRsiStrategy(BaseAStockStrategy):
    """
    布林带 + RSI 均值回归策略

    核心逻辑：
      - 开仓：价格触及布林带下轨（超卖区域）+ RSI < 35（超卖确认）
      - 平仓：① 价格回归至布林带中轨（均线）→ 正常止盈
             ② RSI > 70（超买，获利离场）
             ③ 价格跌破布林带下轨 × stop_loss_mult 倍 → 止损
    """
    params = (
        ('boll_period', 20),
        ('bb_std', 2.0),
        ('rsi_period', 14),
        ('rsi_oversold', 35),
        ('rsi_overbought', 70),
        ('stop_loss_mult', 0.98),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.bollinger = bt.indicators.BollingerBands(
            self.dataclose,
            period=self.p.boll_period,
            devfactor=self.p.bb_std
        )
        self.rsi = bt.indicators.RSI(self.dataclose, period=self.p.rsi_period)
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            touch_lower = self.dataclose[0] <= self.bollinger.lines.bot[0]
            rsi_oversold = self.rsi[0] < self.p.rsi_oversold
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if touch_lower and rsi_oversold and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            reach_mid = self.dataclose[0] >= self.bollinger.lines.mid[0]
            rsi_overbought = self.rsi[0] > self.p.rsi_overbought
            stop_loss_mult = self.dataclose[0] < self.bollinger.lines.bot[0] * self.p.stop_loss_mult
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio or stop_loss_mult
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((reach_mid or rsi_overbought or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class TurtleBreakoutStrategy(BaseAStockStrategy):
    """
    海龟突破策略（唐奇安通道）

    核心逻辑：
      - 开仓：收盘价突破近 N 日最高价（唐奇安上轨）+ 量能放大
      - 止损：ATR 自适应止损（买入价 - atr_mult × ATR14），随价格上移自动追踪
      - 平仓：① ATR追踪止损触发
             ② 收盘价跌破近 exit_period 日最低价（趋势反转）
    """
    params = (
        ('entry_period', 20),
        ('exit_period', 10),
        ('atr_period', 14),
        ('atr_mult', 2.0),
        ('vol_mult', 1.5),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.donchian_high = bt.indicators.Highest(
            self.datahigh, period=self.p.entry_period
        )
        self.donchian_low = bt.indicators.Lowest(
            self.datalow, period=self.p.exit_period
        )
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.vol_ma = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=20
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )
        self.trail_stop = 0

    def notify_order(self, order):
        super().notify_order(order)
        if order.isbuy() and order.status == order.Completed:
            self.trail_stop = self.dataclose[0] - self.atr[0] * self.p.atr_mult

    def next(self):
        if self.order:
            return

        if not self.position:
            price_breakout = self.dataclose[0] > self.donchian_high[-1]
            volume_confirm = self.datavolume[0] > self.vol_ma[0] * self.p.vol_mult
            volume_ok = not self.p.volume_filter or volume_confirm

            if price_breakout and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            if self.trail_stop > 0:
                new_stop = self.dataclose[0] - self.atr[0] * self.p.atr_mult
                if new_stop > self.trail_stop:
                    self.trail_stop = new_stop

            hit_trail_stop = self.dataclose[0] <= self.trail_stop
            trend_reversal = self.dataclose[0] < self.donchian_low[0]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio or hit_trail_stop
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((trend_reversal or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)
                self.trail_stop = 0


class TripleEmaTrendStrategy(BaseAStockStrategy):
    """
    三重EMA趋势 + 量价共振策略

    核心逻辑：
      - 开仓：短期EMA > 中期EMA > 长期EMA（三线多头排列）
             + 当日成交量 > N日均量（量能配合）
             + 短期EMA刚从下方穿过中期EMA（抓早入场时机）
      - 平仓：① 三线空头排列（趋势彻底反转）
             ② 固定止损触发
    """
    params = (
        ('ema_short', 8),
        ('ema_mid', 21),
        ('ema_long', 55),
        ('vol_period', 20),
        ('vol_mult', 1.2),
        ('stop_loss_ratio', 0.07),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.ema_s = bt.indicators.EMA(self.dataclose, period=self.p.ema_short)
        self.ema_m = bt.indicators.EMA(self.dataclose, period=self.p.ema_mid)
        self.ema_l = bt.indicators.EMA(self.dataclose, period=self.p.ema_long)
        self.vol_ma = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=self.p.vol_period
        )
        self.cross = bt.indicators.CrossOver(self.ema_s, self.ema_m)
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            triple_bull = (self.ema_s[0] > self.ema_m[0] > self.ema_l[0])
            just_crossed = self.cross[0] == 1
            vol_confirm = self.datavolume[0] > self.vol_ma[0] * self.p.vol_mult
            volume_ok = not self.p.volume_filter or vol_confirm

            if triple_bull and just_crossed and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            bear_signal = self.ema_s[0] < self.ema_m[0]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((bear_signal or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class KdjMacdResonanceStrategy(BaseAStockStrategy):
    """
    KDJ + MACD 双指标共振策略

    核心逻辑：
      - 开仓：KDJ 金叉（K线上穿D线）发生在超卖区（K < 30）
             同时 MACD 柱状图由负转正（动能转变确认）
      - 平仓：① KDJ 超买死叉（K > 70 + K下穿D）
             ② MACD 柱状图再次由正转负（动能消退）
             ③ 固定止损/止盈
    """
    params = (
        ('kdj_n', 9),
        ('kdj_m1', 3),
        ('kdj_m2', 3),
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('kdj_oversold', 30),
        ('kdj_overbought', 70),
        ('stop_loss_ratio', 0.07),
        ('take_profit_ratio', 0.18),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.stochastic = bt.indicators.Stochastic(
            self.data,
            period=self.p.kdj_n,
            period_dfast=self.p.kdj_m1,
            period_dslow=self.p.kdj_m2
        )
        self.k = self.stochastic.percK
        self.d = self.stochastic.percD
        self.macd = bt.indicators.MACD(
            self.dataclose,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.macd_hist = self.macd.macd - self.macd.signal
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            kdj_gold_cross = (
                self.k[0] > self.d[0] and
                self.k[-1] <= self.d[-1] and
                self.k[0] < self.p.kdj_oversold + 10
            )
            macd_turn_positive = (
                self.macd_hist[0] > 0 and
                self.macd_hist[-1] <= 0
            )
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if kdj_gold_cross and macd_turn_positive and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            kdj_death_cross = (
                self.k[0] < self.d[0] and
                self.k[-1] >= self.d[-1] and
                self.k[0] > self.p.kdj_overbought - 10
            )
            macd_turn_negative = (
                self.macd_hist[0] < 0 and
                self.macd_hist[-1] >= 0
            )
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((kdj_death_cross or macd_turn_negative or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class RsiAtrAdaptiveStrategy(BaseAStockStrategy):
    """
    RSI超卖反弹 + 自适应ATR追踪止损策略

    核心逻辑：
      - 开仓：RSI 从超卖区（<30）向上回升突破 rsi_entry 阈值
             同时价格站上 MA20（中期趋势向好）
      - 追踪止损：随着盈利增加，ATR止损倍数自动收紧
             普通持仓：close - 3.0×ATR
             盈利>8%：close - 2.0×ATR（开始收紧）
             盈利>15%：close - 1.2×ATR（大幅锁定利润）
      - 平仓：① 自适应ATR追踪止损触发
             ② RSI进入超买区（> rsi_exit）且开始回落
             ③ 价格跌破 MA20（中期趋势转弱）
    """
    params = (
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_entry', 35),
        ('rsi_exit', 70),
        ('ma_period', 20),
        ('atr_period', 14),
        ('atr_mult_normal', 3.0),
        ('atr_mult_mid', 2.0),
        ('atr_mult_tight', 1.2),
        ('profit_mid', 0.08),
        ('profit_tight', 0.15),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.rsi = bt.indicators.RSI(self.dataclose, period=self.p.rsi_period)
        self.ma = bt.indicators.SimpleMovingAverage(
            self.dataclose, period=self.p.ma_period
        )
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )
        self._was_oversold = False
        self.trail_stop = 0

    def notify_order(self, order):
        super().notify_order(order)
        if order.isbuy() and order.status == order.Completed:
            self.trail_stop = self.dataclose[0] - self.atr[0] * self.p.atr_mult_normal

    def next(self):
        if self.order:
            if not self.position:
                self._was_oversold = self.rsi[0] < self.p.rsi_oversold
            return

        if not self.position:
            rsi_recovery = (
                self._was_oversold and
                self.rsi[0] >= self.p.rsi_entry and
                self.rsi[-1] < self.p.rsi_entry
            )
            above_ma = self.dataclose[0] > self.ma[0]
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if rsi_recovery and above_ma and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)

            self._was_oversold = self.rsi[0] < self.p.rsi_oversold
        else:
            if self.trail_stop > 0 and self.position_entry_price:
                pnl_pct = (self.dataclose[0] - self.position_entry_price) / self.position_entry_price

                if pnl_pct >= self.p.profit_tight:
                    mult = self.p.atr_mult_tight
                elif pnl_pct >= self.p.profit_mid:
                    mult = self.p.atr_mult_mid
                else:
                    mult = self.p.atr_mult_normal

                new_stop = self.dataclose[0] - self.atr[0] * mult
                if new_stop > self.trail_stop:
                    self.trail_stop = new_stop

            hit_stop = self.dataclose[0] <= self.trail_stop if self.trail_stop > 0 else False
            rsi_peak = (
                self.rsi[0] < self.rsi[-1] and
                self.rsi[-1] > self.p.rsi_exit
            )
            below_ma = self.dataclose[0] < self.ma[0]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio or hit_stop
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((rsi_peak or below_ma or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)
                self.trail_stop = 0

            self._was_oversold = self.rsi[0] < self.p.rsi_oversold


class MacdBollStrategy(BaseAStockStrategy):
    """
    MACD + 布林带组合策略

    核心逻辑：
      - 开仓：MACD金叉（趋势向上）+ 价格在布林带中轨上方（强势区域）
             + 价格从布林带下轨反弹（回调结束）
      - 平仓：MACD死叉（趋势转弱）或 价格跌破布林带中轨（转弱信号）
             + 固定止损保护
    """
    params = (
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('boll_period', 20),
        ('bb_std', 2.0),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.macd = bt.indicators.MACD(
            self.dataclose,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.macd_cross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)
        self.bollinger = bt.indicators.BollingerBands(
            self.dataclose,
            period=self.p.boll_period,
            devfactor=self.p.bb_std
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            macd_golden = self.macd_cross[0] == 1
            above_mid = self.dataclose[0] > self.bollinger.lines.mid[0]
            from_lower = self.dataclose[-1] <= self.bollinger.lines.bot[-1] and self.dataclose[0] > self.bollinger.lines.bot[0]
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if macd_golden and above_mid and from_lower and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            macd_dead = self.macd_cross[0] == -1
            below_mid = self.dataclose[0] < self.bollinger.lines.mid[0]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((macd_dead or below_mid or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class KdjRsiStrategy(BaseAStockStrategy):
    """
    KDJ + RSI 超买超卖策略

    核心逻辑：
      - 开仓：KDJ金叉（K线上穿D线）+ RSI < 30（双重超卖确认）
             + K值 < 20（深度超卖区域）
      - 平仓：KDJ死叉（K线下穿D线）+ RSI > 70（双重超买确认）
             + K值 > 80（深度超买区域）
    """
    params = (
        ('kdj_n', 9),
        ('kdj_m1', 3),
        ('kdj_m2', 3),
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_overbought', 70),
        ('k_oversold', 20),
        ('k_overbought', 80),
        ('stop_loss_ratio', 0.04),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.stochastic = bt.indicators.Stochastic(
            self.data,
            period=self.p.kdj_n,
            period_dfast=self.p.kdj_m1,
            period_dslow=self.p.kdj_m2
        )
        self.k = self.stochastic.percK
        self.d = self.stochastic.percD
        self.kdj_cross = bt.indicators.CrossOver(self.k, self.d)
        self.rsi = bt.indicators.RSI(self.dataclose, period=self.p.rsi_period)
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            kdj_golden = self.kdj_cross[0] == 1
            rsi_oversold = self.rsi[0] < self.p.rsi_oversold
            k_oversold = self.k[0] < self.p.k_oversold
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if kdj_golden and rsi_oversold and k_oversold and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            kdj_dead = self.kdj_cross[0] == -1
            rsi_overbought = self.rsi[0] > self.p.rsi_overbought
            k_overbought = self.k[0] > self.p.k_overbought
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((kdj_dead and rsi_overbought) or k_overbought or stop_loss or take_profit) and t1_ok:
                self.order = self.sell(size=self.position.size)


class MaVolumeStrategy(BaseAStockStrategy):
    """
    均线交叉 + 成交量确认策略

    核心逻辑：
      - 开仓：短期均线上穿长期均线（金叉）
             + 成交量放大（量价配合，确认突破有效性）
             + 价格在所有均线上方（多头排列）
      - 平仓：短期均线下穿长期均线（死叉）
             + 成交量萎缩（动能不足）
             + 固定止损保护
    """
    params = (
        ('ma_short', 10),
        ('ma_long', 30),
        ('ma_trend', 60),
        ('vol_period', 20),
        ('vol_mult', 1.5),
        ('stop_loss_ratio', 0.06),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.ma_s = bt.indicators.SimpleMovingAverage(
            self.dataclose, period=self.p.ma_short
        )
        self.ma_l = bt.indicators.SimpleMovingAverage(
            self.dataclose, period=self.p.ma_long
        )
        self.ma_t = bt.indicators.SimpleMovingAverage(
            self.dataclose, period=self.p.ma_trend
        )
        self.ma_cross = bt.indicators.CrossOver(self.ma_s, self.ma_l)
        self.vol_ma = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=self.p.vol_period
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            ma_golden = self.ma_cross[0] == 1
            vol_confirm = self.datavolume[0] > self.vol_ma[0] * self.p.vol_mult
            above_all = (self.dataclose[0] > self.ma_s[0] > self.ma_l[0] > self.ma_t[0])
            volume_ok = not self.p.volume_filter or vol_confirm

            if ma_golden and volume_ok and above_all:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            ma_dead = self.ma_cross[0] == -1
            vol_weak = self.datavolume[0] < self.vol_ma[0] * 0.7
            below_short = self.dataclose[0] < self.ma_s[0]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if (ma_dead or (vol_weak and below_short) or stop_loss or take_profit) and t1_ok:
                self.order = self.sell(size=self.position.size)


class AtrStopStrategy(BaseAStockStrategy):
    """
    ATR波动率止损策略

    核心逻辑：
      - 开仓：价格突破N日高点（突破信号）+ 成交量配合（确认突破）
      - 止损：基于ATR的动态止损（波动率自适应）
             + 移动止盈（跟踪最高价，回落一定比例止盈）
      - 平仓：动态止损触发 或 移动止盈触发
    """
    params = (
        ('breakout_period', 20),
        ('atr_period', 14),
        ('atr_multiplier', 2.0),
        ('trail_percent', 0.1),
        ('vol_mult', 1.3),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.high_n = bt.indicators.Highest(
            self.datahigh, period=self.p.breakout_period
        )
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.vol_ma = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=20
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )
        self.highest_since_entry = None

    def notify_order(self, order):
        super().notify_order(order)
        if order.isbuy() and order.status == order.Completed:
            self.highest_since_entry = self.dataclose[0]

    def next(self):
        if self.order:
            return

        if not self.position:
            breakout = self.dataclose[0] > self.high_n[0]
            vol_confirm = self.datavolume[0] > self.vol_ma[0] * self.p.vol_mult
            volume_ok = not self.p.volume_filter or vol_confirm

            if breakout and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            if self.highest_since_entry is not None:
                if self.dataclose[0] > self.highest_since_entry:
                    self.highest_since_entry = self.dataclose[0]

                stop_price = self.position_entry_price - self.atr[0] * self.p.atr_multiplier if self.position_entry_price else 0
                atr_stop = self.dataclose[0] < stop_price

                trail_price = self.highest_since_entry * (1 - self.p.trail_percent) if self.highest_since_entry else 0
                trail_stop = self.dataclose[0] < trail_price

                t1_ok = not self.p.t1_rule or (
                    self.position_entry_date and
                    (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
                )
                current_price = self.dataclose[0]
                profit_pct = (current_price - self.position_entry_price) / self.position_entry_price if self.position_entry_price else 0
                stop_loss = profit_pct <= -self.p.stop_loss_ratio or atr_stop
                take_profit = profit_pct >= self.p.take_profit_ratio

                if (atr_stop or trail_stop or stop_loss or take_profit) and t1_ok:
                    self.order = self.sell(size=self.position.size)
                    self.highest_since_entry = None


class CompositeStrategy(BaseAStockStrategy):
    """
    综合多因子策略

    核心逻辑：
      - 开仓：需要同时满足多个条件（严格过滤）
        1. 趋势向上（EMA20 > EMA60）
        2. 动量确认（MACD金叉）
        3. 超卖修复（RSI从<30回升至>40）
        4. 成交量配合（放量）
      - 平仓：任一重要条件转弱即离场
        1. 趋势转弱（EMA20 < EMA60）
        2. 动量转弱（MACD死叉）
        3. 超买（RSI > 70）
        4. 动态止损（基于ATR）
    """
    params = (
        ('ema_short', 20),
        ('ema_long', 60),
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_recovery', 40),
        ('rsi_overbought', 70),
        ('atr_period', 14),
        ('atr_multiplier', 2.5),
        ('vol_mult', 1.4),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.ema_s = bt.indicators.EMA(self.dataclose, period=self.p.ema_short)
        self.ema_l = bt.indicators.EMA(self.dataclose, period=self.p.ema_long)
        self.trend_up = self.ema_s > self.ema_l
        self.macd = bt.indicators.MACD(
            self.dataclose,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.macd_cross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)
        self.rsi = bt.indicators.RSI(self.dataclose, period=self.p.rsi_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.vol_ma = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=20
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )
        self.rsi_recovered = False

    def next(self):
        if not self.position:
            if self.rsi[0] < self.p.rsi_oversold:
                self.rsi_recovered = False
            elif self.rsi[0] > self.p.rsi_recovery:
                self.rsi_recovered = True

        if self.order:
            return

        if not self.position:
            condition1 = self.trend_up[0]
            condition2 = self.macd_cross[0] == 1
            condition3 = self.rsi_recovered
            condition4 = self.datavolume[0] > self.vol_ma[0] * self.p.vol_mult
            volume_ok = not self.p.volume_filter or condition4

            if condition1 and condition2 and condition3 and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
                    self.rsi_recovered = False
        else:
            exit1 = not self.trend_up[0]
            exit2 = self.macd_cross[0] == -1
            exit3 = self.rsi[0] > self.p.rsi_overbought
            stop_price = self.position_entry_price - self.atr[0] * self.p.atr_multiplier if self.position_entry_price else 0
            exit4 = self.dataclose[0] < stop_price

            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price if self.position_entry_price else 0
            stop_loss = profit_pct <= -self.p.stop_loss_ratio or exit4
            take_profit = profit_pct >= self.p.take_profit_ratio

            if (exit1 or exit2 or exit3 or stop_loss or take_profit) and t1_ok:
                self.order = self.sell(size=self.position.size)


class MacdKdjFibonacciStrategy(BaseAStockStrategy):
    """MACD+KDJ共振策略 - 斐波那契参数优化版"""
    params = (
        ('macd_fast', 8),
        ('macd_slow', 21),
        ('macd_signal', 5),
        ('kdj_n', 9),
        ('kdj_m1', 3),
        ('kdj_m2', 3),
        ('stop_loss_ratio', 0.0618),
        ('take_profit_ratio', 0.1618),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.macd = bt.indicators.MACD(
            self.dataclose,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.stochastic = bt.indicators.Stochastic(
            self.data,
            period=self.p.kdj_n,
            period_dfast=self.p.kdj_m1,
            period_dslow=self.p.kdj_m2
        )
        self.k = self.stochastic.percK
        self.d = self.stochastic.percD
        self.j = 3 * self.k - 2 * self.d
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            macd_cross_up = (self.macd.macd[0] > self.macd.signal[0] and
                            self.macd.macd[-1] <= self.macd.signal[-1])
            kdj_cross_up = (self.k[0] > self.d[0] and
                           self.k[-1] <= self.d[-1] and self.k[0] < 50)
            kdj_macd_up = (self.k[0] > self.d[0] and
                          self.k[-1] <= self.d[-1] and self.macd.macd[0] > 0)
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if (macd_cross_up and (kdj_cross_up or kdj_macd_up) and volume_ok):
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            macd_cross_down = (self.macd.macd[0] < self.macd.signal[0] and
                              self.macd.macd[-1] >= self.macd.signal[-1])
            kdj_cross_down = (self.k[0] < self.d[0] and
                             self.k[-1] >= self.d[-1] and self.k[0] > 50)
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((macd_cross_down or kdj_cross_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class BollRsiOptimizedStrategy(BaseAStockStrategy):
    """布林带+RSI策略优化版"""
    params = (
        ('bb_period', 18),
        ('bb_std', 2.2),
        ('rsi_period', 16),
        ('rsi_overbought', 67),
        ('rsi_oversold', 33),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.88),
    )

    def _add_indicators(self):
        self.bollinger = bt.indicators.BollingerBands(
            self.dataclose,
            period=self.p.bb_period,
            devfactor=self.p.bb_std
        )
        self.rsi = bt.indicators.RSI(self.dataclose, period=self.p.rsi_period)
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            below_lower = self.dataclose[0] <= self.bollinger.lines.bot[0]
            rsi_oversold = self.rsi[0] < self.p.rsi_oversold
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )
            if below_lower and rsi_oversold and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            above_mid = self.dataclose[0] >= self.bollinger.lines.mid[0]
            rsi_overbought = self.rsi[0] > self.p.rsi_overbought
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((above_mid or rsi_overbought or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class KdjRsiOptimizedStrategy(BaseAStockStrategy):
    """KDJ+RSI策略优化版"""
    params = (
        ('kdj_n', 10),
        ('kdj_m1', 4),
        ('kdj_m2', 4),
        ('rsi_period', 16),
        ('rsi_overbought', 68),
        ('rsi_oversold', 32),
        ('k_oversold', 22),
        ('k_overbought', 78),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.85),
    )

    def _add_indicators(self):
        self.stochastic = bt.indicators.Stochastic(
            self.data,
            period=self.p.kdj_n,
            period_dfast=self.p.kdj_m1,
            period_dslow=self.p.kdj_m2
        )
        self.k = self.stochastic.percK
        self.d = self.stochastic.percD
        self.j = 3 * self.k - 2 * self.d
        self.rsi = bt.indicators.RSI(self.dataclose, period=self.p.rsi_period)
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            kdj_cross_up = (self.k[0] > self.d[0] and self.k[-1] <= self.d[-1])
            rsi_oversold = self.rsi[0] < self.p.rsi_oversold
            k_oversold = self.k[0] < self.p.k_oversold
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if kdj_cross_up and rsi_oversold and k_oversold and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            kdj_cross_down = (self.k[0] < self.d[0] and self.k[-1] >= self.d[-1])
            rsi_overbought = self.rsi[0] > self.p.rsi_overbought
            k_overbought = self.k[0] > self.p.k_overbought
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((kdj_cross_down and rsi_overbought) or k_overbought or stop_loss or take_profit) and t1_ok:
                self.order = self.sell(size=self.position.size)


class MacdStrategyWithATR(BaseAStockStrategy):
    """MACD策略优化版 - 加入ATR止损和成交量过滤"""
    params = (
        ('macd_fast', 12),
        ('macd_slow', 26),
        ('macd_signal', 9),
        ('atr_period', 14),
        ('atr_multiplier', 2.0),
        ('volume_ma_period', 20),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.8),
    )

    def _add_indicators(self):
        self.macd = bt.indicators.MACD(
            self.dataclose,
            period_me1=self.p.macd_fast,
            period_me2=self.p.macd_slow,
            period_signal=self.p.macd_signal
        )
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.volume_ma = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=self.p.volume_ma_period
        )
        self.stop_loss_price = 0
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def notify_order(self, order):
        super().notify_order(order)
        if order.isbuy() and order.status == order.Completed:
            self.stop_loss_price = self.position_entry_price - self.atr[0] * self.p.atr_multiplier

    def next(self):
        if self.order:
            return

        if not self.position:
            macd_gold_cross = (self.macd.macd[0] > self.macd.signal[0] and
                               self.macd.macd[-1] <= self.macd.signal[-1])
            volume_confirm = self.datavolume[0] > self.volume_ma[0] * 1.1
            volume_ok = not self.p.volume_filter or volume_confirm

            if macd_gold_cross and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            macd_death_cross = (self.macd.macd[0] < self.macd.signal[0] and
                                self.macd.macd[-1] >= self.macd.signal[-1])
            hit_stop_loss = self.dataclose[0] <= self.stop_loss_price if self.stop_loss_price > 0 else False
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio or hit_stop_loss
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((macd_death_cross or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class RsiStrategyWithTrendFilter(BaseAStockStrategy):
    """RSI超买超卖策略优化版 - 加入趋势过滤和布林带确认"""
    params = (
        ('rsi_period', 14),
        ('rsi_overbought', 70),
        ('rsi_oversold', 30),
        ('ma_period', 20),
        ('bb_period', 20),
        ('bb_std', 2.0),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.8),
    )

    def _add_indicators(self):
        self.rsi = bt.indicators.RSI(self.dataclose, period=self.p.rsi_period)
        self.ma = bt.indicators.SimpleMovingAverage(
            self.dataclose, period=self.p.ma_period
        )
        self.bollinger = bt.indicators.BollingerBands(
            self.dataclose,
            period=self.p.bb_period,
            devfactor=self.p.bb_std
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            trend_up = self.dataclose[0] > self.ma[0]
            rsi_oversold = self.rsi[0] < self.p.rsi_oversold
            hit_boll_low = self.dataclose[0] <= self.bollinger.lines.bot[0]
            volume_ok = not self.p.volume_filter or (
                self.datavolume[0] >= self.volume_ma10[0] * self.p.volume_ratio
            )

            if trend_up and rsi_oversold and hit_boll_low and volume_ok:
                cash = self.broker.getcash()
                position_value = cash * self.p.position_ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            rsi_overbought = self.rsi[0] > self.p.rsi_overbought
            hit_boll_mid = self.dataclose[0] >= self.bollinger.lines.mid[0]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((rsi_overbought or hit_boll_mid or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


class TurtleStrategyWithFilter(BaseAStockStrategy):
    """海龟策略优化版 - 加入波动率过滤和成交量确认"""
    params = (
        ('entry_period', 20),
        ('exit_period', 10),
        ('atr_period', 14),
        ('atr_multiplier', 2.0),
        ('volume_ma_period', 20),
        ('stop_loss_ratio', 0.05),
        ('take_profit_ratio', 0.15),
        ('position_ratio', 0.8),
    )

    def _add_indicators(self):
        self.entry_high = bt.indicators.Highest(
            self.datahigh, period=self.p.entry_period
        )
        self.entry_low = bt.indicators.Lowest(
            self.datalow, period=self.p.entry_period
        )
        self.exit_high = bt.indicators.Highest(
            self.datahigh, period=self.p.exit_period
        )
        self.exit_low = bt.indicators.Lowest(
            self.datalow, period=self.p.exit_period
        )
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.volume_ma = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=self.p.volume_ma_period
        )
        self.volume_ma10 = bt.indicators.SimpleMovingAverage(
            self.datavolume, period=10
        )

    def next(self):
        if self.order:
            return

        if not self.position:
            break_up = self.dataclose[0] > self.entry_high[-1]
            volume_confirm = self.datavolume[0] > self.volume_ma[0] * 1.2
            volume_ok = not self.p.volume_filter or volume_confirm

            if break_up and volume_ok:
                atr_normal = self.atr[0] / self.dataclose[0] < 0.05
                ratio = self.p.position_ratio if atr_normal else self.p.position_ratio * 0.5
                cash = self.broker.getcash()
                position_value = cash * ratio
                size = position_value // self.dataclose[0]
                if size > 0:
                    self.order = self.buy(size=size)
        else:
            break_down = self.dataclose[0] < self.exit_low[-1]
            t1_ok = not self.p.t1_rule or (
                self.position_entry_date and
                (self.datas[0].datetime.date(0) - self.position_entry_date).days >= 1
            )
            current_price = self.dataclose[0]
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
            stop_loss = profit_pct <= -self.p.stop_loss_ratio
            take_profit = profit_pct >= self.p.take_profit_ratio

            if ((break_down or stop_loss or take_profit) and t1_ok):
                self.order = self.sell(size=self.position.size)


# ============================================================================
# 策略工厂函数
# ============================================================================

def get_strategy_class(strategy_type):
    """根据策略类型获取对应的Backtrader策略类（完整版，包含所有36个策略）"""
    strategy_map = {
        'macd_kdj': MacdKdjStrategy,
        'rsi': RsiStrategy,
        'bollinger': BollingerStrategy,
        'ma_cross': MaCrossStrategy,
        'kdj_oversold': KdjOversoldStrategy,
        'macd_zero_axis': MacdZeroAxisStrategy,
        'triple_screen': TripleScreenStrategy,
        'turtle_trading': TurtleTradingStrategy,
        'momentum': MomentumStrategy,
        'mean_reversion': MeanReversionStrategy,
        'donchian': DonchianStrategy,
        'williams_r': WilliamsRStrategy,
        'cci': CCIStrategy,
        'ema_cross': EMACrossStrategy,
        'volume_spread': VolumeSpreadStrategy,
        'sar': SARStrategy,
        'keltner': KeltnerChannelStrategy,
        'macd_kdj_fibonacci': MacdKdjFibonacciStrategy,
        'boll_rsi_optimized': BollRsiOptimizedStrategy,
        'kdj_rsi_optimized': KdjRsiOptimizedStrategy,
        'macd_with_atr': MacdStrategyWithATR,
        'rsi_with_trend': RsiStrategyWithTrendFilter,
        'turtle_with_filter': TurtleStrategyWithFilter,
        'ema_rsi': EmaRsiStrategy,
        'dual_macd': DualMacdStrategy,
        'macd': MacdStrategy,
        'boll_rsi': BollRsiStrategy,
        'turtle_breakout': TurtleBreakoutStrategy,
        'triple_ema': TripleEmaTrendStrategy,
        'kdj_macd_resonance': KdjMacdResonanceStrategy,
        'rsi_atr_adaptive': RsiAtrAdaptiveStrategy,
        'macd_boll': MacdBollStrategy,
        'kdj_rsi': KdjRsiStrategy,
        'ma_volume': MaVolumeStrategy,
        'atr_stop': AtrStopStrategy,
        'composite': CompositeStrategy,
    }

    if strategy_type not in strategy_map:
        raise ValueError(f"未知的策略类型: {strategy_type}")

    return strategy_map[strategy_type]


def get_all_strategy_types():
    """获取所有策略类型列表（共36个）"""
    return [
        'macd_kdj', 'rsi', 'bollinger', 'ma_cross', 'kdj_oversold',
        'macd_zero_axis', 'triple_screen', 'turtle_trading', 'momentum',
        'mean_reversion', 'donchian', 'williams_r', 'cci', 'ema_cross',
        'volume_spread', 'sar', 'keltner',
        'macd_kdj_fibonacci', 'boll_rsi_optimized', 'kdj_rsi_optimized',
        'macd_with_atr', 'rsi_with_trend', 'turtle_with_filter',
        'ema_rsi', 'dual_macd', 'macd', 'boll_rsi', 'turtle_breakout',
        'triple_ema', 'kdj_macd_resonance', 'rsi_atr_adaptive',
        'macd_boll', 'kdj_rsi', 'ma_volume', 'atr_stop', 'composite',
    ]


def get_basic_strategy_types():
    """获取策略类型列表（兼容旧接口，返回所有36个策略）"""
    return get_all_strategy_types()


def get_optimized_strategy_types():
    """获取优化策略类型列表（兼容旧接口，返回空列表）"""
    return []


def create_strategy_with_config(strategy_type, config, override_params=None):
    """
    使用配置创建策略类（不使用动态局部类，避免pickle问题）

    参数:
        strategy_type: 策略类型
        config: 配置对象
        override_params: 覆盖参数字典，优先级最高

    返回:
        class: 策略类（直接返回原始类，参数通过cerebro传递）
    """
    strategy_class = get_strategy_class(strategy_type)
    return strategy_class


# 兼容原有接口的类
class AShortStrategy:
    """A股短线策略类 - Backtrader版本"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.strategy_type = config.STRATEGY_TYPE

    def generate_signals(self, df, stock_code=None):
        """生成买卖信号 - 保持原有接口"""
        if df is None or df.empty:
            self.logger.warning("数据为空，无法生成信号")
            return df

        df_signals = df.copy()
        df_signals['signal'] = 0
        return df_signals


if __name__ == "__main__":
    print("=" * 80)
    print("Backtrader策略模块（完整版）测试")
    print("=" * 80)

    # 测试策略工厂
    all_strategies = get_all_strategy_types()

    print(f"\n策略总数: {len(all_strategies)}")
    print("-" * 80)

    # 测试所有策略能否正常加载
    success_count = 0
    failed_count = 0
    failed_list = []

    print("\n测试策略加载...")
    for i, stype in enumerate(all_strategies, 1):
        try:
            strategy_class = get_strategy_class(stype)
            print(f"  [{i:2d}/{len(all_strategies)}] {stype:<25} -> OK (类: {strategy_class.__name__})")
            success_count += 1
        except Exception as e:
            print(f"  [{i:2d}/{len(all_strategies)}] {stype:<25} -> 失败: {e}")
            failed_count += 1
            failed_list.append(stype)

    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    print(f"  总策略数: {len(all_strategies)}")
    print(f"  成功: {success_count}")
    print(f"  失败: {failed_count}")

    if failed_list:
        print(f"\n  失败的策略: {failed_list}")

    print("\n" + "=" * 80)
    print("策略列表")
    print("=" * 80)

    print("\n【全部策略 - 36个】")
    for i, s in enumerate(all_strategies, 1):
        print(f"  {i:2d}. {s}")

    print("\n" + "=" * 80)
    print("策略模块测试完成！")
    print("=" * 80)


# ============================================================================
# 策略类名别名（保持命名一致性）
# ============================================================================

# 策略别名
MacdWithAtr = MacdStrategyWithATR
RsiWithTrend = RsiStrategyWithTrendFilter
TurtleWithFilter = TurtleStrategyWithFilter
