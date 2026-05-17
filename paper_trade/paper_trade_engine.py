# -*- coding: utf-8 -*-
"""
模拟盘核心引擎
负责协调策略运行、信号处理、模拟交易执行
"""
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import pandas as pd
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config
from logger import get_logger
from data_fetcher.data_fetcher import AStockDataFetcher
from paper_trade.trader import PaperTrader
from strategy import get_strategy_class
from utils.atomic_writer import AtomicWriter
from utils.file_rw_lock import FileRWLock


class PaperTradeEngine:
    """模拟盘核心引擎"""

    def __init__(self, config: Config, logger=None, initial_capital: Optional[float] = None):
        """
        初始化模拟盘引擎

        参数:
            config: 配置对象
            logger: 日志对象
            initial_capital: 自定义初始资金，优先级高于配置
        """
        self.config = config
        self.logger = logger or get_logger()
        self.data_fetcher = AStockDataFetcher(config, self.logger)
        self.trader = PaperTrader(config, self.logger, initial_capital=initial_capital)
        self.strategies: List[Tuple[str, callable, float]] = []  # (策略名称, 策略实例, 权重)
        self._loaded = False

    def load_top_strategies(self, top_n: int = 5) -> None:
        """
        加载排名前N的最优策略，自动计算权重

        参数:
            top_n: 使用前N个最优策略
        """
        try:
            # 从最优参数文件中获取策略排名
            best_params = self.config._load_best_params()

            # 按综合表现排序策略
            strategy_scores = []
            for strategy_name, data in best_params.items():
                if 'best_params' not in data:
                    continue
                # 计算综合得分：收益率*0.6 + 夏普比率*0.3 + 胜率*0.1
                score = data.get('avg_return', 0) * 0.6 + data.get('avg_sharpe', 0) * 0.3 + data.get('win_rate', 0) * 0.1
                strategy_scores.append((strategy_name, score, data.get('best_params', {})))

            # 按得分降序排列
            strategy_scores.sort(key=lambda x: x[1], reverse=True)

            # 取前N个策略
            top_strategies = strategy_scores[:top_n]

            if not top_strategies:
                self.logger.warning("未找到已优化的策略，将使用默认策略参数")
                # 使用默认策略
                default_strategies = ['rsi', 'macd', 'bollinger', 'ma_cross', 'kdj_oversold']
                for name in default_strategies[:top_n]:
                    strategy_cls = get_strategy_class(name)
                    strategy = strategy_cls()
                    self.strategies.append((name, strategy, 1.0 / top_n))
                return

            # 计算权重（按得分归一化，先平移得分避免负权重，保证得分越高权重越大）
            min_score = min(s[1] for s in top_strategies)
            # 平移所有得分，保证最小得分为0
            adjusted_scores = [s[1] - min_score for s in top_strategies]
            total_adjusted_score = sum(adjusted_scores)

            for i, (name, score, params) in enumerate(top_strategies):
                if total_adjusted_score > 0:
                    weight = adjusted_scores[i] / total_adjusted_score
                else:
                    # 所有得分相同，平均分配权重
                    weight = 1.0 / len(top_strategies)
                strategy_cls = get_strategy_class(name)
                strategy = strategy_cls(params)
                self.strategies.append((name, strategy, weight))
                self.logger.info(f"加载策略：{name}，权重：{weight:.2f}")

            self._loaded = True

        except Exception as e:
            self.logger.error(f"加载策略失败：{str(e)}", exc_info=True)
            raise

    def generate_strategy_signals(self, stock_code: str, df: pd.DataFrame) -> List[Tuple[int, float]]:
        """
        生成所有策略的交易信号

        参数:
            stock_code: 股票代码
            df: 股票行情数据

        返回:
            信号列表：[(signal, weight)]，signal：1=买入，-1=卖出，0=持有
        """
        signals = []
        for strategy_name, strategy, weight in self.strategies:
            try:
                signal = strategy.generate_signal(df)
                signals.append((signal, weight))
                self.logger.debug(f"策略{strategy_name}对{stock_code}的信号：{signal}")
            except Exception as e:
                self.logger.warning(f"策略{strategy_name}生成信号失败：{str(e)}，信号视为持有")
                signals.append((0, weight))

        return signals

    def aggregate_signals(self, signals: List[Tuple[int, float]]) -> int:
        """
        加权投票聚合信号：达到阈值则执行交易

        参数:
            signals: 信号列表

        返回:
            聚合后的信号：1=买入，-1=卖出，0=持有
        """
        buy_weight = sum(w for s, w in signals if s == 1)
        sell_weight = sum(w for s, w in signals if s == -1)

        threshold = self.config.PAPER_TRADE_SIGNAL_THRESHOLD

        if buy_weight >= threshold and buy_weight > sell_weight:
            return 1
        elif sell_weight >= threshold and sell_weight > buy_weight:
            return -1
        return 0

    def calculate_position_size(self, stock_code: str, current_price: float) -> int:
        """
        计算可买入的仓位大小，不超过单票最大仓位限制

        参数:
            stock_code: 股票代码
            current_price: 当前价格

        返回:
            可买股数，100的整数倍
        """
        max_position_ratio = self.config.PAPER_TRADE_MAX_POSITION_RATIO
        # 单票最大仓位按总资产（现金+持仓总市值）计算，而不是仅按可用现金
        total_assets = self.trader.get_account_summary()['total_value']
        max_position_value = total_assets * max_position_ratio

        # 计算预估费用
        est_fee = self.config.calculate_fees(max_position_value, is_sell=False, stock_code=stock_code)
        available_amount = max_position_value - est_fee

        if available_amount < current_price * 100:  # A股最低买1手=100股
            return 0

        shares = int(available_amount // current_price // 100 * 100)  # 取整到100的倍数
        return shares

    def run_daily_trade(self, trade_date: Optional[str] = None) -> Optional[Dict]:
        """
        运行每日模拟交易

        参数:
            trade_date: 交易日期，格式YYYYMMDD，默认使用当日

        返回:
            交易报告字典
        """
        if trade_date is None:
            trade_date = datetime.now(self.config.TIMEZONE).strftime('%Y%m%d')

        self.logger.info(f"开始运行{trade_date}模拟盘交易")

        try:
            # 加载自选股票池
            stock_pool = self.config.load_stock_pool()
            self.logger.info(f"加载自选股票池，共{len(stock_pool)}只股票")

            if not stock_pool:
                self.logger.warning("股票池为空，无交易可执行")
                return None

            # 加载最新股票数据
            self.logger.info("正在更新最新行情数据...")
            stock_data = {}
            for code in stock_pool:
                try:
                    # 获取最近30个交易日的数据，用于策略计算
                    df = self.data_fetcher.get_stock_data(code, period='daily', count=30)
                    if not df.empty:
                        stock_data[code] = df
                    else:
                        self.logger.warning(f"{code} 无行情数据，跳过")
                except Exception as e:
                    self.logger.warning(f"获取{code}行情数据失败：{str(e)}，跳过")

            if not stock_data:
                self.logger.warning("无有效股票数据，交易取消")
                return None

            # 加载策略（如果未加载）
            if not self._loaded:
                self.load_top_strategies()

            # 多线程并发处理每只股票，最大线程数4
            trade_results = []
            price_dict = {}  # 用于更新所有持仓价格

            def process_single_stock(stock_code: str, df: pd.DataFrame) -> Tuple[Optional[str], Optional[float], Optional[Dict]]:
                """处理单只股票的交易逻辑，线程安全
                返回: (股票代码, 当前价格, 交易结果)
                """
                if df.empty:
                    self.logger.warning(f"{stock_code} 无有效数据，跳过")
                    return None, None, None

                current_price = df['close'].iloc[-1]

                # 生成信号
                signals = self.generate_strategy_signals(stock_code, df)
                aggregated_signal = self.aggregate_signals(signals)

                result = None
                if aggregated_signal == 1:  # 买入信号
                    shares = self.calculate_position_size(stock_code, current_price)
                    if shares > 0:
                        result = self.trader.buy(stock_code, current_price, trade_date, shares)
                        if result:
                            self.logger.info(f"{stock_code} 买入 {shares} 股，价格：{current_price:.2f}")

                elif aggregated_signal == -1:  # 卖出信号
                    position = self.trader.get_position(stock_code)
                    if position and position.shares > 0:
                        result = self.trader.sell(stock_code, current_price, trade_date, position.shares)
                        if result:
                            self.logger.info(f"{stock_code} 卖出 {position.shares} 股，价格：{current_price:.2f}，盈亏：{result['realized_profit']:.2f}")

                return stock_code, current_price, result

            # 使用线程池并发处理
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(process_single_stock, code, df): code for code, df in stock_data.items()}

                for future in as_completed(futures):
                    try:
                        stock_code, current_price, result = future.result()
                        if stock_code and current_price is not None:
                            price_dict[stock_code] = current_price
                        if result:
                            trade_results.append(result)
                    except Exception as e:
                        stock_code = futures[future]
                        self.logger.warning(f"处理股票{stock_code}失败：{str(e)}，跳过")

            # 更新不在股票池中的持仓价格（如果有）
            for code in self.trader.positions:
                if code not in price_dict:
                    try:
                        df = self.data_fetcher.get_stock_data(code, period='daily', count=1)
                        if not df.empty:
                            price_dict[code] = df['close'].iloc[-1]
                    except Exception as e:
                        self.logger.warning(f"更新持仓{code}价格失败：{str(e)}")

            # 更新所有持仓价格
            self.trader.update_prices(price_dict, trade_date)

            # 保存状态
            self._save_state(trade_date)

            # 生成交易报告
            report = self._generate_daily_report(trade_date, trade_results)

            self.logger.info(f"{trade_date}模拟盘交易完成，共{len(trade_results)}笔交易，当前总资产：{self.trader.get_account_summary()['total_value']:.2f}")
            return report

        except Exception as e:
            self.logger.error(f"运行每日交易失败：{str(e)}", exc_info=True)
            return None

    def _save_state(self, trade_date: str) -> None:
        """
        原子化保存模拟盘状态

        参数:
            trade_date: 交易日期
        """
        try:
            state_path = self.config.PAPER_TRADE_DATA_DIR / "current_state.json"
            backup_path = self.config.PAPER_TRADE_DATA_DIR / f"state_backup_{trade_date}.json"

            state = {
                'trade_date': trade_date,
                'cash': self.trader.cash,
                'positions': {code: pos.to_dict() for code, pos in self.trader.positions.items()},
                'trade_records': self.trader.trade_records,
                'daily_portfolios': self.trader.daily_portfolios,
                'initial_capital': self.trader.initial_capital
            }

            # 原子写入，同时备份
            with FileRWLock(str(state_path) + ".lock"):
                AtomicWriter.write_json(state_path, state, ensure_ascii=False, indent=2)
                AtomicWriter.write_json(backup_path, state, ensure_ascii=False, indent=2)

            # 自动清理30天以上的备份文件和报告文件
            try:
                # 清理状态备份
                AtomicWriter.clean_old_backups(self.config.PAPER_TRADE_DATA_DIR, "state_backup_*.json", days=30)
                # 清理交易报告
                report_dir = self.config.PAPER_TRADE_DATA_DIR / "reports"
                AtomicWriter.clean_old_backups(report_dir, "daily_report_*.json", days=30)
            except Exception as e:
                self.logger.warning(f"清理旧备份文件失败：{e}")

            self.logger.debug("模拟盘状态已保存")

        except Exception as e:
            self.logger.error(f"保存状态失败：{str(e)}", exc_info=True)

    def load_state(self) -> bool:
        """
        加载之前的模拟盘状态，加载失败时自动尝试加载最近的备份

        返回:
            是否加载成功
        """
        state_path = self.config.PAPER_TRADE_DATA_DIR / "current_state.json"

        # 先尝试加载当前状态
        if state_path.exists():
            try:
                with FileRWLock(str(state_path) + ".lock").read_lock():
                    state = AtomicWriter.read_json(state_path)

                self.trader.load_state(state)
                self.logger.info(f"成功加载模拟盘状态，上次交易日期：{state.get('trade_date', '未知')}，当前资金：{self.trader.cash:.2f}")
                return True

            except Exception as e:
                self.logger.error(f"加载当前状态失败：{str(e)}，将尝试加载备份文件", exc_info=True)

        # 当前状态加载失败或不存在，尝试加载备份
        backup_files = list(self.config.PAPER_TRADE_DATA_DIR.glob("state_backup_*.json"))
        if not backup_files:
            self.logger.info("无可用的状态备份文件，初始化为新账户")
            return False

        # 按日期倒序排列备份文件，优先加载最新的
        backup_files.sort(reverse=True, key=lambda x: x.stem.split('_')[-1])

        for backup_path in backup_files:
            try:
                self.logger.info(f"尝试加载备份文件：{backup_path.name}")
                with FileRWLock(str(backup_path) + ".lock").read_lock():
                    state = AtomicWriter.read_json(backup_path)

                self.trader.load_state(state)
                self.logger.info(f"成功加载备份状态，上次交易日期：{state.get('trade_date', '未知')}，当前资金：{self.trader.cash:.2f}")
                return True
            except Exception as e:
                self.logger.warning(f"加载备份文件{backup_path.name}失败：{str(e)}，尝试下一个", exc_info=True)

        # 所有备份都加载失败
        self.logger.error("所有状态备份文件都加载失败，初始化为新账户")
        return False

    def _generate_daily_report(self, trade_date: str, trade_results: List[Dict]) -> Dict:
        """
        生成每日交易报告

        参数:
            trade_date: 交易日期
            trade_results: 当日交易结果列表

        返回:
            报告字典
        """
        account = self.trader.get_account_summary()
        report = {
            'trade_date': trade_date,
            'total_trades': len(trade_results),
            'buy_trades': sum(1 for t in trade_results if t['type'] == 'buy'),
            'sell_trades': sum(1 for t in trade_results if t['type'] == 'sell'),
            'total_realized_profit': sum(t.get('realized_profit', 0) for t in trade_results),
            'cash': account['cash'],
            'position_value': account['position_value'],
            'total_value': account['total_value'],
            'total_return_pct': account['total_return_pct'],
            'position_count': account['position_count'],
            'positions': account['positions'],
            'trade_details': trade_results
        }

        # 保存报告到文件
        try:
            report_path = self.config.PAPER_TRADE_DATA_DIR / "reports" / f"daily_report_{trade_date}.json"
            AtomicWriter.write_json(report_path, report, ensure_ascii=False, indent=2)
            self.logger.debug(f"交易报告已保存到：{report_path}")
        except Exception as e:
            self.logger.warning(f"保存报告失败：{str(e)}")

        return report

    def generate_history_report(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """
        生成历史交易报告

        参数:
            start_date: 开始日期，YYYYMMDD
            end_date: 结束日期，YYYYMMDD

        返回:
            历史报告字典
        """
        # 过滤日期范围内的交易记录
        filtered_trades = self.trader.trade_records
        if start_date:
            filtered_trades = [t for t in filtered_trades if t['date'] >= start_date]
        if end_date:
            filtered_trades = [t for t in filtered_trades if t['date'] <= end_date]

        # 过滤日期范围内的每日组合
        filtered_portfolios = self.trader.daily_portfolios
        if start_date:
            filtered_portfolios = [p for p in filtered_portfolios if p['date'] >= start_date]
        if end_date:
            filtered_portfolios = [p for p in filtered_portfolios if p['date'] <= end_date]

        # 计算统计数据
        total_trades = len(filtered_trades)
        buy_trades = sum(1 for t in filtered_trades if t['type'] == 'buy')
        sell_trades = sum(1 for t in filtered_trades if t['type'] == 'sell')
        total_realized_profit = sum(t.get('realized_profit', 0) for t in filtered_trades if t['type'] == 'sell')

        # 计算胜率
        winning_trades = sum(1 for t in filtered_trades if t['type'] == 'sell' and t.get('realized_profit', 0) > 0)
        win_rate = (winning_trades / sell_trades) * 100 if sell_trades > 0 else 0

        # 计算最大回撤
        max_drawdown = 0.0
        if filtered_portfolios:
            peak_value = filtered_portfolios[0]['total_value']
            for portfolio in filtered_portfolios:
                current_value = portfolio['total_value']
                if current_value > peak_value:
                    peak_value = current_value
                drawdown = ((peak_value - current_value) / peak_value) * 100 if peak_value > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        # 获取当前账户信息
        current_account = self.trader.get_account_summary()

        report = {
            'start_date': start_date,
            'end_date': end_date,
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'winning_trades': winning_trades,
            'win_rate': win_rate,
            'total_realized_profit': total_realized_profit,
            'max_drawdown_pct': max_drawdown,
            'current_cash': current_account['cash'],
            'current_position_value': current_account['position_value'],
            'current_total_value': current_account['total_value'],
            'total_return_pct': current_account['total_return_pct'],
            'current_positions': current_account['positions'],
            'recent_trades': filtered_trades[-10:]  # 最近10笔交易
        }

        return report
