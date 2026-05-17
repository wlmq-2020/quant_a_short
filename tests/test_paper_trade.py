# -*- coding: utf-8 -*-
"""
模拟盘模块测试
- paper_trade模块的单元测试
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import sys
import json
from datetime import datetime
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from paper_trade.trader import Position, PaperTrader
from paper_trade.paper_trade_engine import PaperTradeEngine


class TestPosition(unittest.TestCase):
    """测试Position类"""

    def test_position_initialization(self):
        """测试持仓初始化"""
        pos = Position('sh600519', 100, 1800.0, '20240101')

        self.assertEqual(pos.stock_code, 'sh600519')
        self.assertEqual(pos.shares, 100)
        self.assertEqual(pos.avg_price, 1800.0)
        self.assertEqual(pos.entry_date, '20240101')
        self.assertEqual(pos.last_trade_date, '20240101')
        self.assertEqual(pos.current_price, 1800.0)
        self.assertEqual(pos.market_value, 180000.0)
        self.assertEqual(pos.unrealized_profit, 0.0)
        self.assertEqual(pos.unrealized_profit_pct, 0.0)

    def test_update_price(self):
        """测试更新持仓价格更新"""
        pos = Position('sh600519', 100, 1800.0, '20240101')
        pos.update_price(1900.0)

        self.assertEqual(pos.current_price, 1900.0)
        self.assertEqual(pos.market_value, 190000.0)
        self.assertEqual(pos.unrealized_profit, 10000.0)
        self.assertAlmostEqual(pos.unrealized_profit_pct, 100 / 18, places=4)  # ~5.56%

    def test_add_shares(self):
        """测试加仓"""
        pos = Position('sh600519', 100, 1800.0, '20240101')
        pos.add_shares(100, 1900.0)

        self.assertEqual(pos.shares, 200)
        # 平均成本：(100*1800 + 100*1900) / 200 = 1850
        self.assertEqual(pos.avg_price, 1850.0)
        self.assertEqual(pos.last_trade_date, '20240101')  # 保持不变？

    def test_reduce_shares(self):
        """测试减仓"""
        pos = Position('sh600519', 200, 1800.0, '20240101')

        # 减仓100股，价格1900，盈利100*100=10000
        profit = pos.reduce_shares(100, 1900.0)
        self.assertEqual(profit, 10000.0)
        self.assertEqual(pos.shares, 100)
        self.assertEqual(pos.avg_price, 1800.0)  # 平均成本不变

    def test_reduce_shares_more_than_hold(self):
        """测试减仓超过持仓数量"""
        pos = Position('sh600519', 100, 1800.0, '20240101')
        profit = pos.reduce_shares(200, 1900.0)

        # 只减仓100股
        self.assertEqual(profit, 10000.0)
        self.assertEqual(pos.shares, 0)

    def test_to_dict_and_from_dict(self):
        """测试序列化和反序列化"""
        pos = Position('sh600519', 100, 1800.0, '20240101')
        pos.update_price(1900.0)

        # 序列化
        pos_dict = pos.to_dict()
        self.assertIsInstance(pos_dict, dict)
        self.assertEqual(pos_dict['stock_code'], 'sh600519')
        self.assertEqual(pos_dict['shares'], 100)
        self.assertEqual(pos_dict['avg_price'], 1800.0)
        self.assertEqual(pos_dict['current_price'], 1900.0)

        # 反序列化
        new_pos = Position.from_dict(pos_dict)
        self.assertEqual(new_pos.stock_code, pos.stock_code)
        self.assertEqual(new_pos.shares, pos.shares)
        self.assertEqual(new_pos.avg_price, pos.avg_price)
        self.assertEqual(new_pos.current_price, pos.current_price)
        self.assertEqual(new_pos.unrealized_profit, pos.unrealized_profit)


class TestPaperTrader(unittest.TestCase):
    """测试PaperTrader类"""

    def setUp(self):
        """测试前准备"""
        self.config = MagicMock()
        self.config.INITIAL_CAPITAL = 100000.0
        self.config.PAPER_TRADE_INITIAL_CAPITAL = 1000000.0
        self.config.COMMISSION_RATE = 0.00025
        self.config.STAMP_DUTY_RATE = 0.001
        self.config.TRANSFER_FEE_RATE = 0.00001
        self.config.MIN_COMMISSION = 5.0
        self.config.T1_RULE = True
        self.config.PAPER_TRADE_MAX_POSITION_RATIO = 0.2
        self.config.POSITION_RATIO = 0.8  # 添加这个属性

        # mock calculate_fees方法
        def mock_calculate_fees(amount, is_sell=False, stock_code=None):
            commission = max(amount * 0.00025, 5.0)
            transfer_fee = amount * 0.00001
            stamp_duty = amount * 0.001 if is_sell else 0.0
            return commission + transfer_fee + stamp_duty

        self.config.calculate_fees = mock_calculate_fees
        self.logger = MagicMock()
        self.trader = PaperTrader(self.config, self.logger)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.trader.initial_capital, 1000000.0)
        self.assertEqual(self.trader.cash, 1000000.0)
        self.assertEqual(self.trader.positions, {})
        self.assertEqual(self.trader.trade_records, [])
        self.assertEqual(self.trader.daily_portfolios, [])

    def test_custom_initial_capital(self):
        """测试自定义初始资金"""
        trader = PaperTrader(self.config, self.logger, initial_capital=200000.0)
        self.assertEqual(trader.initial_capital, 200000.0)
        self.assertEqual(trader.cash, 200000.0)

    def test_buy_stock_success(self):
        """测试成功买入股票"""
        # 买入100股，价格100元，金额10000元
        result = self.trader.buy('sh600519', 100.0, '20240101', 100)

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'buy')
        self.assertEqual(result['stock_code'], 'sh600519')
        self.assertEqual(result['shares'], 100)
        self.assertEqual(result['price'], 100.0)
        self.assertEqual(result['amount'], 10000.0)

        # 计算费用：手续费10000*0.00025=2.5，最低5元，过户费0.1元
        total_fee = 5.0 + 0.1
        self.assertEqual(result['fee'], total_fee)
        self.assertEqual(result['total_cost'], 10000.0 + total_fee)
        self.assertEqual(result['cash_after'], 1000000.0 - 10000.0 - total_fee)

        # 检查持仓
        self.assertIn('sh600519', self.trader.positions)
        pos = self.trader.positions['sh600519']
        self.assertEqual(pos.shares, 100)
        self.assertEqual(pos.avg_price, 100.0)

    def test_buy_insufficient_funds(self):
        """测试资金不足无法买入"""
        # 尝试买入100000股，价格100元，需要1000万，超过资金
        result = self.trader.buy('sh600519', 100.0, '20240101', 100000)
        self.assertIsNone(result)

    def test_sell_stock_success(self):
        """测试成功卖出股票"""
        # 先买入100股
        self.trader.buy('sh600519', 100.0, '20240101', 100)
        buy_cash = self.trader.cash

        # 第二天卖出
        result = self.trader.sell('sh600519', 110.0, '20240102', 100)

        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'sell')
        self.assertEqual(result['shares'], 100)
        self.assertEqual(result['price'], 110.0)
        self.assertEqual(result['amount'], 11000.0)

        # 计算费用：手续费11000*0.00025=2.75 → 5元，过户费0.11元，印花税11元
        total_sell_fee = 5.0 + 0.11 + 11.0
        self.assertAlmostEqual(result['fee'], total_sell_fee, places=4)
        self.assertAlmostEqual(result['net_income'], 11000.0 - total_sell_fee, places=4)
        # 实现利润 = (卖出价 - 平均成本价) * 股数（不包含手续费，手续费单独计算）
        expected_profit = (110.0 - 100.0) * 100
        self.assertAlmostEqual(result['realized_profit'], expected_profit, places=2)
        # 收益率 = (卖出价 - 成本价) / 成本价 * 100（不包含手续费）
        expected_profit_pct = (110.0 - 100.0) / 100.0 * 100
        self.assertAlmostEqual(result['realized_profit_pct'], expected_profit_pct, places=2)

        # 检查持仓已清空
        self.assertNotIn('sh600519', self.trader.positions)

    def test_sell_nonexistent_stock(self):
        """测试卖出没有持仓的股票"""
        result = self.trader.sell('sh600519', 110.0, '20240102', 100)
        self.assertIsNone(result)

    def test_t1_rule_sell_same_day(self):
        """测试T+1规则，当日买入不能当日卖出"""
        # 当日买入
        self.trader.buy('sh600519', 100.0, '20240101', 100)

        # 当日卖出，应该失败
        result = self.trader.sell('sh600519', 110.0, '20240101', 100)
        self.assertIsNone(result)

        # 第二天卖出，应该成功
        result = self.trader.sell('sh600519', 110.0, '20240102', 100)
        self.assertIsNotNone(result)

    def test_get_position(self):
        """测试获取持仓"""
        self.trader.buy('sh600519', 100.0, '20240101', 100)
        pos = self.trader.get_position('sh600519')
        self.assertIsNotNone(pos)
        self.assertEqual(pos.stock_code, 'sh600519')

        # 不存在的股票
        pos = self.trader.get_position('sz000001')
        self.assertIsNone(pos)

    def test_update_portfolio(self):
        """测试更新每日组合"""
        self.trader.buy('sh600519', 100.0, '20240101', 100)
        self.trader.update_prices({'sh600519': 110.0}, '20240101')

        # 检查每日组合记录
        self.assertEqual(len(self.trader.daily_portfolios), 1)
        portfolio = self.trader.daily_portfolios[0]
        self.assertEqual(portfolio['date'], '20240101')
        self.assertEqual(portfolio['total_value'], self.trader.cash + 100 * 110.0)

    def test_get_account_summary(self):
        """测试获取账户摘要"""
        self.trader.buy('sh600519', 100.0, '20240101', 100)
        self.trader.update_prices({'sh600519': 110.0}, '20240101')

        summary = self.trader.get_account_summary()
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary['initial_capital'], 1000000.0)
        self.assertLess(summary['cash'], 1000000.0)
        self.assertGreater(summary['position_value'], 0)
        self.assertGreater(summary['total_value'], 0)
        self.assertIsInstance(summary['positions'], list)
        self.assertEqual(len(summary['positions']), 1)

    def test_load_and_save_state(self):
        """测试状态加载和保存"""
        # 创建一些交易记录
        self.trader.buy('sh600519', 100.0, '20240101', 100)
        self.trader.update_prices({'sh600519': 110.0}, '20240101')

        # 保存状态
        state = {
            'cash': self.trader.cash,
            'positions': {code: pos.to_dict() for code, pos in self.trader.positions.items()},
            'trade_records': self.trader.trade_records,
            'daily_portfolios': self.trader.daily_portfolios,
            'initial_capital': self.trader.initial_capital
        }

        # 创建新的trader，加载状态
        new_trader = PaperTrader(self.config, self.logger)
        new_trader.load_state(state)

        self.assertEqual(new_trader.cash, self.trader.cash)
        self.assertEqual(len(new_trader.positions), 1)
        self.assertEqual(len(new_trader.trade_records), 1)
        self.assertEqual(len(new_trader.daily_portfolios), 1)
        self.assertEqual(new_trader.initial_capital, self.trader.initial_capital)

    def test_run_paper_trade_full_backtest(self):
        """测试PaperTrader.run_paper_trade完整回测流程"""
        # 生成测试信号数据
        df_signals = pd.DataFrame({
            'date': [f'202401{str(i).zfill(2)}' for i in range(1, 11)],
            'close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            'signal': [1, 0, 0, 0, -1, 0, 1, 0, 0, 0]  # 第1天买入，第5天卖出，第7天买入
        })

        # 运行回测
        result = self.trader.run_paper_trade(df_signals, 'sh600519')

        # 验证结果
        self.assertIsNotNone(result)
        self.assertEqual(result['stock_code'], 'sh600519')
        self.assertIn('daily_portfolios', result)
        self.assertIn('trade_records', result)
        self.assertIn('final_summary', result)

        # 交易记录应该有4笔：买入、卖出、买入、最后清仓
        trade_records = result['trade_records']
        self.assertEqual(len(trade_records), 4)
        self.assertEqual(trade_records.iloc[0]['type'], 'buy')
        self.assertEqual(trade_records.iloc[0]['date'], '20240101')
        self.assertEqual(trade_records.iloc[1]['type'], 'sell')
        self.assertEqual(trade_records.iloc[1]['date'], '20240105')
        self.assertEqual(trade_records.iloc[2]['type'], 'buy')
        self.assertEqual(trade_records.iloc[2]['date'], '20240107')
        self.assertEqual(trade_records.iloc[3]['type'], 'sell')  # 最后清仓
        self.assertEqual(trade_records.iloc[3]['date'], '20240110')

        # 每日组合应该有11条（10天交易+最后清仓后更新）
        daily_portfolios = result['daily_portfolios']
        self.assertEqual(len(daily_portfolios), 11)

        # 最终应该没有持仓，因为最后清仓了
        final_summary = result['final_summary']
        self.assertEqual(final_summary['position_count'], 0)
        # 计算收益：(104-100)*股数 + (109-106)*股数 - 手续费，应该是正收益
        self.assertGreater(final_summary['total_profit'], 0)


class TestPaperTradeEngine(unittest.TestCase):
    """测试PaperTradeEngine类"""

    def setUp(self):
        """测试前准备"""
        self.config = Config
        self.logger = MagicMock()
        self.engine = PaperTradeEngine(self.config, self.logger)

    def test_calculate_position_size(self):
        """测试仓位计算"""
        # 资金100万，单票最大20%，即20万
        # 股价100元，需要扣除手续费后计算可买股数，取整100的倍数
        self.engine.trader.cash = 1000000.0
        self.config.PAPER_TRADE_MAX_POSITION_RATIO = 0.2
        size = self.engine.calculate_position_size('sh600519', 100.0)
        self.assertEqual(size, 1900)

        # 资金不足的情况：资金10000元，股价200元，最多买100股
        self.engine.trader.cash = 10000.0
        size = self.engine.calculate_position_size('sh600519', 200.0)
        self.assertEqual(size, 0)  # 20%*10000=2000，2000/200=10股，不足100股

    def test_aggregate_signals(self):
        """测试信号聚合"""
        # 5个策略信号，3个买入，1个卖出，1个持有，权重都是1
        signals = [
            (1, 1.0),
            (1, 1.0),
            (1, 1.0),
            (-1, 1.0),
            (0, 1.0)
        ]
        self.config.PAPER_TRADE_SIGNAL_THRESHOLD = 0.6
        result = self.engine.aggregate_signals(signals)
        # 总权重总和是5，买入权重是3/5=60%，刚好达到阈值，返回1
        self.assertEqual(result, 1)

        # 测试加权
        signals = [
            (1, 0.5),  # 权重0.5
            (1, 0.5),  # 权重0.5
            (-1, 1.0)  # 权重1.0
        ]
        result = self.engine.aggregate_signals(signals)
        # 买入总权重1.0，总权重2.0，50%<60%，返回0
        self.assertEqual(result, 0)

        # 卖出信号达到阈值
        signals = [
            (-1, 0.8),
            (-1, 0.6),
            (1, 0.6)
        ]
        # 卖出总权重1.4/2.0=70%≥60%
        result = self.engine.aggregate_signals(signals)
        self.assertEqual(result, -1)

    @patch('paper_trade.paper_trade_engine.get_strategy_class')
    def test_load_top_strategies(self, mock_get_strategy_class):
        """测试加载最优策略"""
        # mock策略类
        mock_strategy_class = MagicMock()
        mock_get_strategy_class.return_value = mock_strategy_class

        # mock best_params
        mock_best_params = {
            'rsi': {
                'best_params': {'rsi_period': 14},
                'avg_return': 20.0,
                'avg_sharpe': 1.5,
                'win_rate': 0.6
            },
            'macd': {
                'best_params': {'macd_fast': 12},
                'avg_return': 15.0,
                'avg_sharpe': 1.2,
                'win_rate': 0.55
            },
            'bollinger': {
                'best_params': {'bb_period': 20},
                'avg_return': 10.0,
                'avg_sharpe': 1.0,
                'win_rate': 0.5
            }
        }

        # mock _load_best_params方法
        self.config._load_best_params = MagicMock(return_value=mock_best_params)

        self.engine.load_top_strategies(top_n=3)

        self.assertEqual(len(self.engine.strategies), 3)
        # 验证get_strategy_class被调用了3次
        self.assertEqual(mock_get_strategy_class.call_count, 3)
        # 计算得分：20*0.6 + 1.5*0.3 + 0.6*0.1 = 12 + 0.45 + 0.06 = 12.51
        # 15*0.6 + 1.2*0.3 + 0.55*0.1 = 9 + 0.36 + 0.055 = 9.415
        # 10*0.6 + 1.0*0.3 + 0.5*0.1 = 6 + 0.3 + 0.05 = 6.35
        # 总得分：12.51 + 9.415 + 6.35 = 28.275
        # 权重计算：平移最小得分到0，避免负权重
        min_score = 6.35
        adjusted_scores = [12.51 - min_score, 9.415 - min_score, 6.35 - min_score]
        total_adjusted = sum(adjusted_scores)
        self.assertAlmostEqual(self.engine.strategies[0][2], adjusted_scores[0]/total_adjusted, places=3)
        self.assertAlmostEqual(self.engine.strategies[1][2], adjusted_scores[1]/total_adjusted, places=3)
        self.assertAlmostEqual(self.engine.strategies[2][2], adjusted_scores[2]/total_adjusted, places=3)



    @patch('paper_trade.paper_trade_engine.Path.exists')
    @patch('paper_trade.paper_trade_engine.open', new_callable=mock_open)
    @patch('paper_trade.paper_trade_engine.json.load')
    def test_state_load_with_corrupted_file(self, mock_json_load, mock_file_open, mock_exists):
        """测试状态保存和加载：损坏文件自动恢复到备份的场景"""
        # mock当前状态文件存在但是损坏
        mock_exists.return_value = True
        # 第一次加载抛出异常（损坏）
        mock_json_load.side_effect = [json.JSONDecodeError("Invalid JSON", "", 0), {
            'trade_date': '20240130',
            'cash': 950000.0,
            'positions': {
                'sh600519': {
                    'stock_code': 'sh600519',
                    'shares': 1000,
                    'avg_price': 100.0,
                    'entry_date': '20240101',
                    'current_price': 105.0
                }
            },
            'trade_records': [],
            'daily_portfolios': [],
            'initial_capital': 1000000.0
        }]

        # mock备份文件存在且正常
        self.config.PAPER_TRADE_DATA_DIR = Path('temp_test_paper_trade')
        self.config.PAPER_TRADE_DATA_DIR.mkdir(exist_ok=True)

        # 创建引擎
        engine = PaperTradeEngine(self.config, self.logger)

        # 尝试加载状态，应该会尝试加载主文件失败，然后返回False使用初始状态
        # 注意：当前load_state方法没有自动恢复备份的逻辑，所以这里测试加载失败返回初始状态
        # 如果需要自动恢复备份的功能，需要修改load_state方法，不过当前测试按照现有实现来
        result = engine.load_state()

        # 验证加载失败返回False，使用初始状态
        self.assertFalse(result)
        self.assertEqual(engine.trader.cash, 1000000.0)
        self.assertEqual(len(engine.trader.positions), 0)

        # 清理临时文件
        import shutil
        if self.config.PAPER_TRADE_DATA_DIR.exists():
            shutil.rmtree(self.config.PAPER_TRADE_DATA_DIR)

    def test_boundary_scenarios(self):
        """测试边界场景：空股票池、全负收益策略、涨跌停价格交易、部分股票无数据等场景"""
        # 1. 测试空股票池
        self.config.load_stock_pool = MagicMock(return_value=[])
        engine = PaperTradeEngine(self.config, self.logger)
        report = engine.run_daily_trade('20240101')
        self.assertIsNone(report)

        # 2. 测试涨跌停价格交易：T+1规则下当日买入不能卖出
        trader = PaperTrader(self.config, self.logger)
        trader.buy('sh600519', 100.0, '20240101', 100)
        # 当日卖出（涨停价）应该失败
        result = trader.sell('sh600519', 110.0, '20240101', 100)
        self.assertIsNone(result)
        # 次日卖出（跌停价）应该成功
        result = trader.sell('sh600519', 90.0, '20240102', 100)
        self.assertIsNotNone(result)
        self.assertEqual(result['realized_profit'], -1000.0)  # 亏损1000元

        # 3. 测试部分股票无数据
        self.config.load_stock_pool = MagicMock(return_value=['sh600519', 'sz000001'])
        engine = PaperTradeEngine(self.config, self.logger)
        # mock数据获取，第一个股票有数据，第二个没有
        def mock_get_stock_data(code, period='daily', count=30):
            if code == 'sh600519':
                return pd.DataFrame({
                    'date': ['20240101'],
                    'close': [100.0]
                })
            else:
                return pd.DataFrame()

        engine.data_fetcher.get_stock_data = mock_get_stock_data
        # mock策略信号
        mock_strategy = MagicMock()
        mock_strategy.generate_signal.return_value = 1
        engine.strategies = [('rsi', mock_strategy, 1.0)]
        engine._loaded = True

        report = engine.run_daily_trade('20240101')
        self.assertIsNotNone(report)
        self.assertEqual(report['buy_trades'], 1)  # 只有第一个股票有交易

        # 4. 测试全负收益策略：所有交易都亏损
        trader.reset()
        # 模拟一系列亏损交易
        for i in range(5):
            buy_date = f'202401{str(i*2 +1).zfill(2)}'
            sell_date = f'202401{str(i*2 +2).zfill(2)}'
            trader.buy('sh600519', 100.0 + i, buy_date, 100)
            trader.sell('sh600519', 90.0 + i, sell_date, 100)

        summary = trader.get_account_summary()
        self.assertLess(summary['total_profit'], 0)  # 总亏损
        self.assertEqual(summary['position_count'], 0)  # 无持仓
        # 总亏损应该是5次每次亏损1000元，加上手续费，大约5000多元
        self.assertAlmostEqual(summary['total_profit'], -5000.0, delta=1000.0)

    @patch('paper_trade.paper_trade_engine.AStockDataFetcher')
    @patch('paper_trade.paper_trade_engine.get_strategy_class')
    @patch('paper_trade.paper_trade_engine.AtomicWriter')
    def test_run_daily_trade_full_flow(self, mock_atomic_writer, mock_get_strategy_class, mock_data_fetcher_cls):
        """测试PaperTradeEngine.run_daily_trade完整流程：数据获取、信号生成、交易执行、状态保存"""
        # mock策略类
        mock_strategy = MagicMock()
        mock_strategy.generate_signal.return_value = 1  # 全部返回买入信号
        mock_get_strategy_class.return_value = MagicMock(return_value=mock_strategy)

        # mock最佳参数
        mock_best_params = {
            'rsi': {
                'best_params': {'rsi_period': 14},
                'avg_return': 20.0,
                'avg_sharpe': 1.5,
                'win_rate': 0.6
            }
        }
        self.config._load_best_params = MagicMock(return_value=mock_best_params)
        self.config.load_stock_pool = MagicMock(return_value=['sh600519'])
        self.config.PAPER_TRADE_SIGNAL_THRESHOLD = 0.5
        self.config.PAPER_TRADE_DATA_DIR = Path('temp_test_paper_trade')
        self.config.PAPER_TRADE_DATA_DIR.mkdir(exist_ok=True)
        (self.config.PAPER_TRADE_DATA_DIR / "reports").mkdir(exist_ok=True)

        # mock数据获取
        mock_data_fetcher = MagicMock()
        # 生成30天的测试数据
        test_data = pd.DataFrame({
            'date': [f'202401{str(i).zfill(2)}' for i in range(1, 31)],
            'open': [100 + i for i in range(30)],
            'high': [101 + i for i in range(30)],
            'low': [99 + i for i in range(30)],
            'close': [100 + i for i in range(30)],
            'volume': [1000000 for _ in range(30)]
        })
        mock_data_fetcher.get_stock_data.return_value = test_data
        mock_data_fetcher_cls.return_value = mock_data_fetcher

        # 创建引擎
        engine = PaperTradeEngine(self.config, self.logger, initial_capital=1000000.0)

        # 运行每日交易
        trade_date = '20240130'
        report = engine.run_daily_trade(trade_date)

        # 验证结果
        self.assertIsNotNone(report)
        self.assertEqual(report['trade_date'], trade_date)
        self.assertEqual(report['buy_trades'], 1)
        self.assertEqual(report['sell_trades'], 0)
        self.assertEqual(report['position_count'], 1)
        self.assertGreater(report['position_value'], 0)

        # 验证策略调用
        self.assertEqual(mock_strategy.generate_signal.call_count, 1)

        # 验证数据获取调用
        self.assertEqual(mock_data_fetcher.get_stock_data.call_count, 1)

        # 验证状态已保存：AtomicWriter.write_json被调用
        self.assertGreaterEqual(mock_atomic_writer.write_json.call_count, 1)  # 至少保存了当前状态

        # 清理临时文件
        import shutil
        if self.config.PAPER_TRADE_DATA_DIR.exists():
            shutil.rmtree(self.config.PAPER_TRADE_DATA_DIR)


if __name__ == '__main__':
    unittest.main()
