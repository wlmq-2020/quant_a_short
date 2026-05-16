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
    - 过户费：双向收取，成交金额的万分之0.1（沪市股票收取，深市股票免收）
    """
    params = (
        ('commission', 0.00025),  # 佣金费率万分之2.5
        ('stamp_duty', 0.001),     # 印花税千分之1，卖出时收取
        ('transfer_fee', 0.00001), # 过户费万分之0.1，双向收取
        ('min_commission', 5.0),   # 单笔最低佣金5元
        ('stock_code', None),      # 股票代码，用于判断沪市/深市
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

        # 使用公共工具类计算交易费用，保持全局逻辑一致
        from utils.common_utils import CommonUtils
        return CommonUtils.calculate_trade_fees(
            amount=trade_amount,
            is_sell=size < 0,
            stock_code=self.p.stock_code
        )

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
