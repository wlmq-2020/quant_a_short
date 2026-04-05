# -*- coding: utf-8 -*-
"""
组合策略回测与优化模块
提供真实策略回测、组合净值计算、策略轮动回测功能
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime
from collections import defaultdict

from config import Config
from logger.logger import GlobalLogger


class RealStrategyBacktester:
    """真实策略回测器 - 基于真实回测引擎"""
    
    def __init__(self):
        self.logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level="INFO",
            retention_days=7
        )
    
    def run_all_strategies_real(self, stock_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        """
        运行所有17个策略的真实回测
        
        参数:
            stock_data: 股票数据字典 {stock_code: df}
            
        返回:
            {strategy_name: portfolio_value_series}
        """
        from backtest.backtester import StrategyComparator, BacktraderBacktester
        
        self.logger.info("="*80)
        self.logger.info("运行所有策略真实回测")
        self.logger.info("="*80)
        
        strategy_values = {}
        
        # 1. 运行所有策略回测
        comparator = StrategyComparator(Config, self.logger)
        all_results = comparator.run_all_strategies_backtest(stock_data)
        
        # 2. 计算每个策略的组合净值
        self.logger.info("\n计算各策略组合净值...")
        
        for strategy_name, stock_results in all_results.items():
            self.logger.info(f"  处理策略: {strategy_name}")
            
            # 计算该策略的组合净值
            portfolio_value = self._calculate_strategy_portfolio(stock_results)
            strategy_values[strategy_name] = portfolio_value
        
        self.logger.info("="*80)
        self.logger.info("✅ 所有策略真实回测完成！")
        self.logger.info("="*80)
        
        return strategy_values
    
    def _calculate_strategy_portfolio(self, stock_results: Dict) -> pd.Series:
        """
        计算单个策略的组合净值（等权配置所有股票）
        
        参数:
            stock_results: 单策略的各股票回测结果
            
        返回:
            组合净值时间序列
        """
        if not stock_results:
            return pd.Series()
        
        # 获取所有日期索引
        all_dates = set()
        for stock_code, result in stock_results.items():
            if result and 'value_series' in result:
                all_dates.update(result['value_series'].index)
        
        if not all_dates:
            return pd.Series()
        
        all_dates = sorted(all_dates)
        
        # 等权计算组合净值
        n_stocks = len(stock_results)
        portfolio_values = []
        
        for date in all_dates:
            total_value = 0.0
            count = 0
            
            for stock_code, result in stock_results.items():
                if result and 'value_series' in result:
                    if date in result['value_series'].index:
                        total_value += result['value_series'].loc[date]
                        count += 1
            
            if count > 0:
                avg_value = total_value / count
                portfolio_values.append(avg_value)
            else:
                # 无数据时使用前值
                if portfolio_values:
                    portfolio_values.append(portfolio_values[-1])
                else:
                    portfolio_values.append(Config.INITIAL_CAPITAL)
        
        return pd.Series(portfolio_values, index=all_dates)


class PortfolioRotationTester:
    """策略轮动回测器"""
    
    def __init__(self):
        self.logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level="INFO",
            retention_days=7
        )
    
    def run_monthly_rotation(self, strategy_values: Dict[str, pd.Series], 
                             market_prices: pd.Series = None) -> pd.Series:
        """
        运行月度策略轮动回测
        
        参数:
            strategy_values: 各策略净值时间序列
            market_prices: 市场基准价格（用于市场状态识别）
            
        返回:
            轮动组合净值时间序列
        """
        from strategy.market_state import MarketStateDetector, StrategyRotator
        
        self.logger.info("="*80)
        self.logger.info("月度策略轮动回测")
        self.logger.info("="*80)
        
        # 对齐所有策略时间索引
        values_df = pd.DataFrame(strategy_values).dropna()
        
        if market_prices is None:
            # 如果没有市场价格，用第一个策略的净值作为代理
            market_prices = values_df.iloc[:, 0]
        
        detector = MarketStateDetector()
        rotator = StrategyRotator(detector)
        
        # 按月分组
        monthly_groups = values_df.groupby(pd.Grouper(freq='ME'))
        
        rotation_portfolio_values = []
        current_strategies = list(strategy_values.keys())[:4]  # 初始用前4个
        current_weights = {s: 1/len(current_strategies) for s in current_strategies}
        
        self.logger.info("\n--- 月度轮动 ---")
        
        for month_end, month_data in monthly_groups:
            # 用截至月底的数据判断市场状态
            state = detector.detect(market_prices.loc[:month_end])
            recommended = rotator.get_recommended_strategies(market_prices.loc[:month_end])
            
            # 判断是否需要轮动
            if rotator.should_rotate(current_strategies, market_prices.loc[:month_end]):
                self.logger.info(f"  {month_end.strftime('%Y-%m')}: 状态={state:12} -> 轮动到: {recommended[:4]}")
                current_strategies = recommended[:4]
                current_weights = {s: 1/len(current_strategies) for s in current_strategies}
            else:
                self.logger.info(f"  {month_end.strftime('%Y-%m')}: 状态={state:12} -> 保持")
            
            # 计算当月组合收益
            month_returns = month_data[current_strategies].pct_change().dropna()
            
            for date in month_returns.index:
                portfolio_return = 0.0
                for s in current_strategies:
                    if s in month_returns.columns:
                        portfolio_return += month_returns.loc[date, s] * current_weights[s]
                
                if rotation_portfolio_values:
                    new_value = rotation_portfolio_values[-1] * (1 + portfolio_return)
                else:
                    new_value = Config.INITIAL_CAPITAL * (1 + portfolio_return)
                
                rotation_portfolio_values.append(new_value)
        
        # 创建净值序列
        rotation_value_series = pd.Series(
            rotation_portfolio_values,
            index=values_df.index[-len(rotation_portfolio_values):]
        )
        
        # 计算指标
        total_return = (rotation_value_series.iloc[-1] / rotation_value_series.iloc[0] - 1) * 100
        
        self.logger.info(f"\n--- 轮动结果 ---")
        self.logger.info(f"  总收益率: {total_return:.2f}%")
        
        return rotation_value_series


def save_portfolio_results(strategy_values: Dict[str, pd.Series], 
                          rotation_value: pd.Series = None):
    """保存组合回测结果"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 保存策略净值
    values_df = pd.DataFrame(strategy_values)
    values_path = Config.REPORTS_DIR / f"phase2/real_strategy_values_{timestamp}.csv"
    values_df.to_csv(values_path)
    print(f"真实策略净值已保存: {values_path}")
    
    # 保存最新版本
    latest_values_path = Config.REPORTS_DIR / "phase2/real_strategy_values_latest.csv"
    values_df.to_csv(latest_values_path)
    
    # 保存轮动结果
    if rotation_value is not None:
        rotation_path = Config.REPORTS_DIR / f"phase2/rotation_portfolio_{timestamp}.csv"
        rotation_value.to_csv(rotation_path)
        print(f"轮动组合净值已保存: {rotation_path}")
        
        latest_rotation_path = Config.REPORTS_DIR / "phase2/rotation_portfolio_latest.csv"
        rotation_value.to_csv(latest_rotation_path)


if __name__ == '__main__':
    print("="*80)
    print("组合策略回测与优化模块")
    print("="*80)
    print("\n主要类:")
    print("  - RealStrategyBacktester: 真实策略回测")
    print("  - PortfolioRotationTester: 策略轮动回测")
    print("\n使用示例:")
    print("  from strategy.portfolio_optimizer import RealStrategyBacktester, PortfolioRotationTester")
    print("  backtester = RealStrategyBacktester()")
    print("  strategy_values = backtester.run_all_strategies_real(stock_data)")
    print("  rotation_tester = PortfolioRotationTester()")
    print("  rotation_value = rotation_tester.run_monthly_rotation(strategy_values)")
    print("\n" + "="*80)
