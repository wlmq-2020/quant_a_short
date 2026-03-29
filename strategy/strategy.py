# -*- coding: utf-8 -*-
"""
A股短线策略模块 - Backtrader版本
提供多种A股高胜率短线策略
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


# 策略工厂函数
def get_strategy_class(strategy_type):
    """根据策略类型获取对应的Backtrader策略类"""
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
    }

    if strategy_type not in strategy_map:
        raise ValueError(f"未知的策略类型: {strategy_type}")

    return strategy_map[strategy_type]


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
    print("Backtrader策略模块测试...")

    # 测试策略工厂
    all_strategies = [
        'macd_kdj', 'rsi', 'bollinger', 'ma_cross',
        'kdj_oversold', 'macd_zero_axis', 'triple_screen', 'turtle_trading',
        'momentum', 'mean_reversion', 'donchian', 'williams_r',
        'cci', 'ema_cross', 'volume_spread', 'sar', 'keltner'
    ]

    for stype in all_strategies:
        try:
            strategy_class = get_strategy_class(stype)
            print(f"策略 '{stype}' 获取成功")
        except Exception as e:
            print(f"策略 '{stype}' 获取失败: {e}")

    print("策略模块测试完成！")
