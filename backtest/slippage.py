# -*- coding: utf-8 -*-
"""
A股滑点计算类，根据股票市值大小不同设置不同滑点
"""
import backtrader as bt


class MarketCapSlippage:
    """
    基于市值的滑点模型：
    - 大盘股（上证50/沪深300成分股）：默认0.1%滑点
    - 中小盘股（其他股票）：默认0.3%滑点
    """
    params = (
        ('large_cap_slippage', 0.001),  # 大盘股滑点0.1%
        ('small_cap_slippage', 0.003),  # 中小盘股滑点0.3%
        # 上证50成分股代码（2024年版）
        ('sz50_stocks', {
            'sh600000', 'sh600036', 'sh600104', 'sh600519', 'sh600028',
            'sh600030', 'sh601318', 'sh601668', 'sh601288', 'sh601988',
            'sh601857', 'sh601398', 'sh600050', 'sh601166', 'sh601601',
            'sh601328', 'sh600111', 'sh600019', 'sh601006', 'sh601186',
            'sh601628', 'sh601766', 'sh601989', 'sh601899', 'sh601390',
            'sh601169', 'sh601088', 'sh600016', 'sh600018', 'sh600009',
            'sh600010', 'sh600031', 'sh600085', 'sh600089', 'sh600115',
            'sh600150', 'sh600177', 'sh600309', 'sh600547', 'sh600585',
            'sh600690', 'sh600837', 'sh600887', 'sh600893', 'sh601009',
            'sh601099', 'sh601111', 'sh601299', 'sh601669', 'sh601939'
        }),
        # 沪深300成分股代码（部分，这里简化处理，主要的大盘股）
        ('hs300_stocks', {
            'sh600000', 'sh600016', 'sh600028', 'sh600030', 'sh600036',
            'sh600048', 'sh600050', 'sh600104', 'sh600111', 'sh600196',
            'sh600276', 'sh600309', 'sh600519', 'sh600585', 'sh600690',
            'sh600703', 'sh600745', 'sh600809', 'sh600837', 'sh600887',
            'sh600893', 'sh601012', 'sh601088', 'sh601166', 'sh601169',
            'sh601288', 'sh601318', 'sh601336', 'sh601398', 'sh601601',
            'sh601628', 'sh601658', 'sh601668', 'sh601818', 'sh601857',
            'sh601888', 'sh601899', 'sh601919', 'sh601939', 'sh601988',
            'sz000001', 'sz000002', 'sz000333', 'sz000538', 'sz000568',
            'sz000596', 'sz000651', 'sz000725', 'sz000858', 'sz000895',
            'sz002304', 'sz002415', 'sz002475', 'sz002594', 'sz300059',
            'sz300122', 'sz300124', 'sz300347', 'sz300498', 'sz300750'
        })
    )

    def __init__(self):
        super().__init__()
        # 合并大盘股列表
        self.large_cap_stocks = self.p.sz50_stocks.union(self.p.hs300_stocks)

    def _get_slippage(self, size, price, stock_code):
        """
        获取对应股票的滑点
        :param size: 交易数量
        :param price: 当前价格
        :param stock_code: 股票代码
        :return: 滑点调整后的价格
        """
        # 判断是大盘股还是中小盘股
        if stock_code in self.large_cap_stocks:
            slippage = self.p.large_cap_slippage
        else:
            slippage = self.p.small_cap_slippage

        # 买入时价格上浮，卖出时价格下浮
        if size > 0:  # 买入
            return price * (1 + slippage)
        else:  # 卖出
            return price * (1 - slippage)

    def __call__(self, order, price, ago):
        """
        滑点处理的核心方法
        :param order: 订单对象
        :param price: 原始价格
        :param ago: 时间偏移
        :return: 滑点调整后的价格
        """
        stock_code = order.data._name
        slippage_price = self._get_slippage(order.size, price, stock_code)

        # 确保价格不为负
        return max(slippage_price, 0.001)
