# -*- coding: utf-8 -*-
"""
A股交易佣金计算类，完全匹配实盘交易规则
"""
import backtrader as bt


class AStockCommission(bt.CommInfoBase):
    """
    A股交易佣金/费用计算类，完全符合实盘规则：
    - 佣金：双向收取，成交金额的万分之2.5，单笔最低5元
    - 印花税：卖出时收取，成交金额的千分之1，买入时不收取
    - 过户费：双向收取，成交金额的万分之0.1（沪市股票收取，深市股票免收，这里统一计算）
    """
    params = (
        ('commission', 0.00025),  # 佣金费率万分之2.5
        ('stamp_duty', 0.001),     # 印花税千分之1，卖出时收取
        ('transfer_fee', 0.00001), # 过户费万分之0.1，双向收取
        ('min_commission', 5.0),   # 单笔最低佣金5元
        ('percabs', True),         # 按百分比计算
        ('stocklike', True),       # 股票类资产
        ('commtype', bt.CommInfoBase.COMM_PERC), # 佣金类型为百分比
    )

    def _getcommission(self, size, price, pseudoexec):
        """
        计算交易佣金
        :param size: 交易数量，正数为买入，负数为卖出
        :param price: 成交价格
        :param pseudoexec: 是否是伪执行（用于计算保证金等）
        :return: 总交易费用（佣金+印花税+过户费）
        """
        if size == 0:
            return 0.0

        # 计算成交金额
        trade_amount = abs(size) * price

        # 计算佣金，最低5元
        commission = max(trade_amount * self.p.commission, self.p.min_commission)

        # 计算过户费，双向收取
        transfer_fee = trade_amount * self.p.transfer_fee

        # 计算印花税，仅卖出时收取
        stamp_duty = 0.0
        if size < 0:  # 卖出
            stamp_duty = trade_amount * self.p.stamp_duty

        # 总费用
        total_fee = commission + transfer_fee + stamp_duty

        return total_fee

    def getvaluesize(self, size, price):
        """
        计算头寸价值
        """
        return abs(size) * price

    def getoperationcost(self, size, price):
        """
        计算交易的操作成本
        """
        return self._getcommission(size, price, True)
