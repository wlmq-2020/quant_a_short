# -*- coding: utf-8 -*-
"""
优化策略模块 - 完整版本
包含 temp/t 目录下所有优化策略，适配 BaseAStockStrategy 架构

整合的策略列表：
1. EmaRsiStrategy - 双EMA+RSI过滤策略
2. DualMacdStrategy - 双线确认MACD策略 v5（重要优化策略）
3. MacdStrategy - 基础MACD策略
4. BollRsiStrategy - 布林带+RSI均值回归策略
5. TurtleBreakoutStrategy - 海龟突破策略（唐奇安通道）
6. TripleEmaTrendStrategy - 三重EMA趋势+量价共振策略
7. KdjMacdResonanceStrategy - KDJ+MACD双指标共振策略
8. RsiAtrAdaptiveStrategy - RSI超卖反弹+自适应ATR追踪止损
9. MacdBollStrategy - MACD+布林带组合策略
10. KdjRsiStrategy - KDJ+RSI超买超卖策略
11. MaVolumeStrategy - 均线交叉+成交量确认策略
12. AtrStopStrategy - ATR波动率止损策略
13. CompositeStrategy - 综合多因子策略
+ 原始6个优化策略（共19个）
"""
import pandas as pd
import numpy as np
import backtrader as bt
from strategy.strategy import BaseAStockStrategy


# ============================================================================
# 策略1：双EMA+RSI过滤策略
# ============================================================================
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


# ============================================================================
# 策略2：双线确认MACD策略 v5（重要优化策略）
# ============================================================================
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


# ============================================================================
# 策略3：基础MACD策略
# ============================================================================
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


# ============================================================================
# 策略4：布林带 + RSI 均值回归策略
# ============================================================================
class BollRsiStrategy(BaseAStockStrategy):
    """
    策略1：布林带 + RSI 均值回归策略

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


# ============================================================================
# 策略2：海龟突破策略（唐奇安通道）
# ============================================================================
class TurtleBreakoutStrategy(BaseAStockStrategy):
    """
    策略2：海龟突破策略（唐奇安通道）

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


# ============================================================================
# 策略3：三重EMA趋势 + 量价共振策略
# ============================================================================
class TripleEmaTrendStrategy(BaseAStockStrategy):
    """
    策略3：三重EMA趋势 + 量价共振策略

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


# ============================================================================
# 策略4：KDJ + MACD 双指标共振策略
# ============================================================================
class KdjMacdResonanceStrategy(BaseAStockStrategy):
    """
    策略4：KDJ + MACD 双指标共振策略

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


# ============================================================================
# 策略5：RSI超卖反弹 + 自适应ATR追踪止损策略
# ============================================================================
class RsiAtrAdaptiveStrategy(BaseAStockStrategy):
    """
    策略5：RSI超卖反弹 + 自适应ATR追踪止损策略

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


# ============================================================================
# 策略6：MACD + 布林带组合策略
# ============================================================================
class MacdBollStrategy(BaseAStockStrategy):
    """
    策略6：MACD + 布林带组合策略

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


# ============================================================================
# 策略7：KDJ + RSI 超买超卖策略
# ============================================================================
class KdjRsiStrategy(BaseAStockStrategy):
    """
    策略7：KDJ + RSI 超买超卖策略

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


# ============================================================================
# 策略8：均线交叉 + 成交量确认策略
# ============================================================================
class MaVolumeStrategy(BaseAStockStrategy):
    """
    策略8：均线交叉 + 成交量确认策略

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


# ============================================================================
# 策略9：ATR波动率止损策略
# ============================================================================
class AtrStopStrategy(BaseAStockStrategy):
    """
    策略9：ATR波动率止损策略

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


# ============================================================================
# 策略10：综合多因子策略
# ============================================================================
class CompositeStrategy(BaseAStockStrategy):
    """
    策略10：综合多因子策略

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


# ============================================================================
# 策略工厂函数
# ============================================================================
def get_optimized_strategy_class(strategy_type):
    """根据策略类型获取对应的优化策略类"""
    strategy_map = {
        # 原始的6个优化策略
        'macd_kdj_fibonacci': MacdKdjFibonacciStrategy,
        'boll_rsi_optimized': BollRsiOptimizedStrategy,
        'kdj_rsi_optimized': KdjRsiOptimizedStrategy,
        'macd_with_atr': MacdStrategyWithATR,
        'rsi_with_trend': RsiStrategyWithTrendFilter,
        'turtle_with_filter': TurtleStrategyWithFilter,
        # 新增的13个策略
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
        raise ValueError(f"未知的优化策略类型: {strategy_type}")

    return strategy_map[strategy_type]


def get_all_optimized_strategy_types():
    """获取所有优化策略类型列表"""
    return [
        # 原始的6个优化策略
        'macd_kdj_fibonacci',
        'boll_rsi_optimized',
        'kdj_rsi_optimized',
        'macd_with_atr',
        'rsi_with_trend',
        'turtle_with_filter',
        # 新增的13个策略
        'ema_rsi',
        'dual_macd',
        'macd',
        'boll_rsi',
        'turtle_breakout',
        'triple_ema',
        'kdj_macd_resonance',
        'rsi_atr_adaptive',
        'macd_boll',
        'kdj_rsi',
        'ma_volume',
        'atr_stop',
        'composite',
    ]


# 保持原有6个策略类的向后兼容（定义在文件末尾，避免引用问题）
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


if __name__ == "__main__":
    print("优化策略模块（完整版）测试...")

    # 测试策略工厂
    all_strategies = get_all_optimized_strategy_types()

    for stype in all_strategies:
        try:
            strategy_class = get_optimized_strategy_class(stype)
            print(f"优化策略 '{stype}' 获取成功")
        except Exception as e:
            print(f"优化策略 '{stype}' 获取失败: {e}")

    print(f"\n共 {len(all_strategies)} 个优化策略测试完成！")
