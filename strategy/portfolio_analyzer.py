# -*- coding: utf-8 -*-
"""
组合策略分析模块
提供策略相关性分析、组合回测、轮动回测功能
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from collections import defaultdict
from config import Config


class StrategyCorrelationAnalyzer:
    """策略相关性分析器"""
    
    def __init__(self, strategy_list: List[str] = None):
        """
        初始化相关性分析器
        
        参数:
            strategy_list: 策略列表，默认使用所有已优化策略
        """
        if strategy_list is None:
            self.strategy_list = Config.get_all_optimized_strategies()
        else:
            self.strategy_list = strategy_list
        
        self.returns_data = {}
        self.correlation_matrix = None
    
    def analyze_strategy_returns(self, strategy_returns: Dict[str, pd.Series]) -> pd.DataFrame:
        """
        分析策略收益率相关性
        
        参数:
            strategy_returns: {策略名: 收益率序列}
            
        返回:
            相关性矩阵 DataFrame
        """
        self.returns_data = strategy_returns
        
        # 对齐时间索引
        returns_df = pd.DataFrame(strategy_returns)
        returns_df = returns_df.dropna()
        
        # 计算相关性矩阵
        self.correlation_matrix = returns_df.corr()
        
        return self.correlation_matrix
    
    def get_low_correlation_pairs(self, threshold: float = 0.3) -> List[Tuple[str, str, float]]:
        """
        获取低相关策略对
        
        参数:
            threshold: 相关性阈值，低于此值认为低相关
            
        返回:
            [(策略1, 策略2, 相关系数), ...]
        """
        if self.correlation_matrix is None:
            return []
        
        pairs = []
        n = len(self.correlation_matrix.columns)
        
        for i in range(n):
            for j in range(i+1, n):
                corr = self.correlation_matrix.iloc[i, j]
                if abs(corr) < threshold:
                    pairs.append((
                        self.correlation_matrix.index[i],
                        self.correlation_matrix.columns[j],
                        corr
                    ))
        
        # 按相关系数绝对值排序
        pairs.sort(key=lambda x: abs(x[2]))
        return pairs
    
    def recommend_portfolio(self, n_strategies: int = 4) -> List[str]:
        """
        推荐低相关组合
        
        参数:
            n_strategies: 组合策略数量
            
        返回:
            推荐的策略列表
        """
        if self.correlation_matrix is None:
            return self.strategy_list[:n_strategies]
        
        # 简单贪心算法：选择相关性最低的组合
        selected = []
        remaining = list(self.correlation_matrix.columns)
        
        # 先选表现最好的策略（这里简化处理）
        if remaining:
            selected.append(remaining[0])
            remaining.pop(0)
        
        # 逐步添加与已选策略相关性最低的
        while len(selected) < n_strategies and remaining:
            avg_corrs = []
            for s in remaining:
                # 计算与已选策略的平均相关系数
                corrs = [abs(self.correlation_matrix.loc[s, sel]) for sel in selected]
                avg_corr = np.mean(corrs)
                avg_corrs.append((s, avg_corr))
            
            # 选平均相关性最低的
            avg_corrs.sort(key=lambda x: x[1])
            best_strategy = avg_corrs[0][0]
            
            selected.append(best_strategy)
            remaining.remove(best_strategy)
        
        return selected


class PortfolioBacktester:
    """组合策略回测器"""
    
    def __init__(self, initial_capital: float = 100000.0):
        """
        初始化组合回测器
        
        参数:
            initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
    
    def backtest_equal_weight(self, strategy_returns: Dict[str, pd.Series], 
                               weights: Dict[str, float] = None) -> pd.Series:
        """
        等权重组合回测
        
        参数:
            strategy_returns: {策略名: 收益率序列}
            weights: 权重字典，None表示等权
            
        返回:
            组合净值序列
        """
        returns_df = pd.DataFrame(strategy_returns).dropna()
        
        if weights is None:
            # 等权重
            n = len(returns_df.columns)
            weights = {s: 1.0/n for s in returns_df.columns}
        
        # 计算组合收益率
        portfolio_returns = pd.Series(0.0, index=returns_df.index)
        
        for strategy, weight in weights.items():
            if strategy in returns_df.columns:
                portfolio_returns += returns_df[strategy] * weight
        
        # 计算净值
        portfolio_value = (1 + portfolio_returns).cumprod() * self.initial_capital
        
        return portfolio_value
    
    def calculate_metrics(self, portfolio_value: pd.Series) -> Dict:
        """
        计算组合表现指标
        
        参数:
            portfolio_value: 组合净值序列
            
        返回:
            指标字典
        """
        returns = portfolio_value.pct_change().dropna()
        
        total_return = (portfolio_value.iloc[-1] / portfolio_value.iloc[0] - 1) * 100
        annual_return = (1 + total_return/100) ** (252/len(returns)) - 1 if len(returns) > 0 else 0
        
        # 最大回撤
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() * 100
        
        # 夏普比率（假设无风险利率3%）
        risk_free_rate = 0.03
        excess_returns = returns - risk_free_rate/252
        sharpe = np.sqrt(252) * excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0
        
        # 卡尔马比率
        calmar = annual_return / abs(max_drawdown/100) if max_drawdown != 0 else 0
        
        return {
            'total_return_pct': total_return,
            'annual_return_pct': annual_return * 100,
            'max_drawdown_pct': max_drawdown,
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'final_value': portfolio_value.iloc[-1]
        }


# ========== 预设组合回测 ==========

def run_phase2_analysis():
    """
    运行 Phase 2 完整分析
    (需要真实回测数据时使用)
    """
    print("="*80)
    print("Phase 2: 组合策略分析")
    print("="*80)
    print("\n注意：此函数需要策略回测收益率数据作为输入")
    print("使用示例:")
    print("  1. 先获取各策略的净值/收益率数据")
    print("  2. 调用 StrategyCorrelationAnalyzer.analyze_strategy_returns()")
    print("  3. 调用 PortfolioBacktester.backtest_equal_weight()")
    print("\n" + "="*80)


if __name__ == '__main__':
    print("="*80)
    print("组合策略分析模块")
    print("="*80)
    print("\n主要类:")
    print("  - StrategyCorrelationAnalyzer: 策略相关性分析")
    print("  - PortfolioBacktester: 组合回测")
    print("\n使用示例:")
    print("  from strategy.portfolio_analyzer import StrategyCorrelationAnalyzer, PortfolioBacktester")
    print("  analyzer = StrategyCorrelationAnalyzer()")
    print("  corr_matrix = analyzer.analyze_strategy_returns(strategy_returns)")
    print("  backtester = PortfolioBacktester()")
    print("  portfolio_value = backtester.backtest_equal_weight(strategy_returns, weights)")
    print("\n" + "="*80)
