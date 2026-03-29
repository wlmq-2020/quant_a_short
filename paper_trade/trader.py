# -*- coding: utf-8 -*-
"""
模拟交易模块
负责模拟盘交易、账户管理、持仓管理
"""
import pandas as pd
from datetime import datetime
from pathlib import Path


class Position:
    """持仓类"""

    def __init__(self, stock_code, shares, avg_price, entry_date):
        self.stock_code = stock_code
        self.shares = shares
        self.avg_price = avg_price
        self.entry_date = entry_date
        self.holding_days = 0
        self.last_trade_date = entry_date

    def update_price(self, current_price):
        """更新当前价格计算盈亏"""
        self.current_price = current_price
        self.market_value = self.shares * current_price
        self.unrealized_profit = (current_price - self.avg_price) * self.shares
        self.unrealized_profit_pct = ((current_price - self.avg_price) / self.avg_price) * 100

    def add_shares(self, shares, price):
        """加仓"""
        total_shares = self.shares + shares
        total_cost = self.shares * self.avg_price + shares * price
        self.avg_price = total_cost / total_shares
        self.shares = total_shares

    def reduce_shares(self, shares, price):
        """减仓，返回实现的盈亏"""
        if shares > self.shares:
            shares = self.shares

        realized_profit = (price - self.avg_price) * shares
        self.shares -= shares

        return realized_profit


class PaperTrader:
    """模拟交易类"""

    def __init__(self, config, logger):
        """
        初始化模拟交易器

        参数:
            config: 配置对象
            logger: 日志对象
        """
        self.config = config
        self.logger = logger
        self.initial_capital = config.INITIAL_CAPITAL
        self.cash = config.INITIAL_CAPITAL
        self.positions = {}  # {stock_code: Position}
        self.trade_records = []
        self.daily_portfolios = []

    def reset(self):
        """重置模拟交易"""
        self.cash = self.initial_capital
        self.positions = {}
        self.trade_records = []
        self.daily_portfolios = []
        self.logger.info("模拟交易账户已重置")

    def get_account_summary(self):
        """获取账户摘要"""
        total_position_value = sum(p.market_value for p in self.positions.values())
        total_assets = self.cash + total_position_value
        total_profit = total_assets - self.initial_capital
        total_profit_pct = (total_profit / self.initial_capital) * 100 if self.initial_capital > 0 else 0

        return {
            'initial_capital': self.initial_capital,
            'cash': self.cash,
            'total_position_value': total_position_value,
            'total_assets': total_assets,
            'total_profit': total_profit,
            'total_profit_pct': total_profit_pct,
            'position_count': len(self.positions)
        }

    def buy(self, stock_code, price, date, shares=None):
        """
        买入股票

        参数:
            stock_code: 股票代码
            price: 买入价格
            date: 日期
            shares: 股数（为None则自动计算）

        返回:
            dict: 交易结果
        """
        # T+1检查：当日是否有卖出
        if self.config.T1_RULE:
            if self._check_t1_sell(stock_code, date):
                self.logger.warning(f"{date} {stock_code} T+1限制：当日卖出后不可买入")
                return None

        if shares is None:
            # 计算可买股数
            position_ratio = self.config.POSITION_RATIO
            available_cash = self.cash * position_ratio
            est_fee = self.config.calculate_fees(available_cash, is_sell=False)
            shares = int((available_cash - est_fee) / price / 100) * 100

        if shares < 100:
            self.logger.warning(f"{date} 可买股数不足100股，放弃买入")
            return None

        buy_amount = shares * price
        fee = self.config.calculate_fees(buy_amount, is_sell=False)
        total_cost = buy_amount + fee

        if total_cost > self.cash:
            self.logger.warning(f"{date} 资金不足，需要{total_cost:.2f}，可用{self.cash:.2f}")
            return None

        # 执行买入
        self.cash -= total_cost

        if stock_code in self.positions:
            self.positions[stock_code].add_shares(shares, price)
        else:
            self.positions[stock_code] = Position(stock_code, shares, price, date)

        # 更新持仓当前价格
        self.positions[stock_code].update_price(price)
        self.positions[stock_code].last_trade_date = date

        # 记录交易
        trade_record = {
            'date': date,
            'type': 'buy',
            'stock_code': stock_code,
            'shares': shares,
            'price': price,
            'amount': buy_amount,
            'fee': fee,
            'total_cost': total_cost,
            'cash_after': self.cash
        }
        self.trade_records.append(trade_record)

        self.logger.info(f"{date} 买入 {stock_code} {shares}股，价格{price:.2f}，花费{total_cost:.2f}")
        return trade_record

    def sell(self, stock_code, price, date, shares=None):
        """
        卖出股票

        参数:
            stock_code: 股票代码
            price: 卖出价格
            date: 日期
            shares: 股数（为None则清仓）

        返回:
            dict: 交易结果
        """
        if stock_code not in self.positions:
            self.logger.warning(f"{date} {stock_code} 无持仓，无法卖出")
            return None

        position = self.positions[stock_code]

        # T+1检查
        if self.config.T1_RULE:
            if date <= position.last_trade_date:
                self.logger.warning(f"{date} {stock_code} T+1限制：当日买入不可卖出")
                return None

        if shares is None:
            shares = position.shares

        if shares > position.shares:
            shares = position.shares

        # 计算费用
        sell_amount = shares * price
        fee = self.config.calculate_fees(sell_amount, is_sell=True)
        net_income = sell_amount - fee

        # 计算实现盈亏
        realized_profit = position.reduce_shares(shares, price)
        realized_profit_pct = ((price - position.avg_price) / position.avg_price) * 100

        # 更新现金
        self.cash += net_income

        # 如果持仓为0，删除
        if position.shares == 0:
            del self.positions[stock_code]
        else:
            position.last_trade_date = date

        # 记录交易
        trade_record = {
            'date': date,
            'type': 'sell',
            'stock_code': stock_code,
            'shares': shares,
            'price': price,
            'amount': sell_amount,
            'fee': fee,
            'net_income': net_income,
            'realized_profit': realized_profit,
            'realized_profit_pct': realized_profit_pct,
            'cash_after': self.cash
        }
        self.trade_records.append(trade_record)

        self.logger.info(f"{date} 卖出 {stock_code} {shares}股，价格{price:.2f}，收入{net_income:.2f}，盈亏{realized_profit:.2f}")
        return trade_record

    def _check_t1_sell(self, stock_code, date):
        """检查当日是否有卖出记录"""
        for record in reversed(self.trade_records):
            if record['date'] != date:
                break
            if record['type'] == 'sell' and record['stock_code'] == stock_code:
                return True
        return False

    def update_prices(self, price_dict, date):
        """
        更新所有持仓价格

        参数:
            price_dict: {stock_code: current_price}
            date: 日期
        """
        for stock_code, price in price_dict.items():
            if stock_code in self.positions:
                self.positions[stock_code].update_price(price)

        # 记录当日组合
        summary = self.get_account_summary()
        summary['date'] = date
        self.daily_portfolios.append(summary)

    def get_positions_dataframe(self):
        """获取持仓DataFrame"""
        if not self.positions:
            return pd.DataFrame()

        data = []
        for stock_code, pos in self.positions.items():
            data.append({
                'stock_code': stock_code,
                'shares': pos.shares,
                'avg_price': pos.avg_price,
                'current_price': pos.current_price,
                'market_value': pos.market_value,
                'unrealized_profit': pos.unrealized_profit,
                'unrealized_profit_pct': pos.unrealized_profit_pct,
                'entry_date': pos.entry_date
            })

        return pd.DataFrame(data)

    def get_trade_records_dataframe(self):
        """获取交易记录DataFrame"""
        if not self.trade_records:
            return pd.DataFrame()
        return pd.DataFrame(self.trade_records)

    def get_daily_portfolios_dataframe(self):
        """获取每日组合DataFrame"""
        if not self.daily_portfolios:
            return pd.DataFrame()
        return pd.DataFrame(self.daily_portfolios)

    def run_paper_trade(self, df_signals, stock_code):
        """
        运行模拟交易

        参数:
            df_signals: 包含信号的数据
            stock_code: 股票代码

        返回:
            dict: 模拟交易结果
        """
        self.logger.info(f"开始 {stock_code} 模拟交易")
        self.reset()

        df = df_signals.reset_index(drop=True)

        for i in range(len(df)):
            row = df.iloc[i]
            date = row['date']
            close = row['close']
            signal = row['signal']

            # 更新持仓价格
            self.update_prices({stock_code: close}, date)

            # 执行交易
            if signal == 1:
                self.buy(stock_code, close, date)
            elif signal == -1:
                self.sell(stock_code, close, date)

        # 最后一天清仓
        if stock_code in self.positions:
            last_row = df.iloc[-1]
            self.sell(stock_code, last_row['close'], last_row['date'])

        # 最后再更新一次
        if len(df) > 0:
            last_date = df.iloc[-1]['date']
            last_close = df.iloc[-1]['close']
            self.update_prices({stock_code: last_close}, last_date)

        # 生成结果
        result = {
            'daily_portfolios': self.get_daily_portfolios_dataframe(),
            'trade_records': self.get_trade_records_dataframe(),
            'final_summary': self.get_account_summary(),
            'stock_code': stock_code
        }

        summary = result['final_summary']
        self.logger.info(f"模拟交易完成，最终收益: {summary['total_profit_pct']:.2f}%")
        return result
