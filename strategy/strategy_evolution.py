# -*- coding: utf-8 -*-
"""
策略进化与动态更新系统 - 统一版
整合 v2.0 的所有改进
- 多指标综合评分
- 统计分布分析
- 自动淘汰阈值
- 自动更新 config.py（不依赖 astor）
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
import json

from config import Config
from logger.logger import GlobalLogger


class StrategyEvolutionSystem:
    """策略进化系统 - 统一版"""
    
    def __init__(self):
        self.logger = GlobalLogger(
            log_dir=Config.LOG_DIR,
            log_level="INFO",
            retention_days=7
        )
        self.strategy_metrics = {}
        self.composite_scores = {}
    
    def load_strategy_data(self) -> Tuple[Dict, Dict]:
        """加载策略数据"""
        values_path = Config.REPORTS_DIR / "phase2/strategy_values_latest.csv"
        returns_path = Config.REPORTS_DIR / "phase2/strategy_returns_latest.csv"
        
        if not values_path.exists() or not returns_path.exists():
            self.logger.warning("未找到策略数据")
            return {}, {}
        
        values_df = pd.read_csv(values_path, index_col=0)
        returns_df = pd.read_csv(returns_path, index_col=0)
        
        strategy_values = {col: values_df[col] for col in values_df.columns}
        strategy_returns = {col: returns_df[col] for col in returns_df.columns}
        
        self.logger.info(f"已加载 {len(strategy_values)} 个策略数据")
        self.logger.info(f"  交易日数: {len(values_df)}")
        
        return strategy_values, strategy_returns
    
    def calculate_comprehensive_metrics(self, strategy_values: Dict, 
                                       strategy_returns: Dict) -> Dict:
        """计算综合指标"""
        from strategy.portfolio_analyzer import PortfolioBacktester
        
        backtester = PortfolioBacktester(initial_capital=100000)
        
        self.strategy_metrics = {}
        
        for strategy_name, value_series in strategy_values.items():
            metrics = backtester.calculate_metrics(value_series)
            
            returns = strategy_returns[strategy_name]
            metrics['return_volatility'] = returns.std() * np.sqrt(252)
            metrics['downside_risk'] = returns[returns < 0].std() * np.sqrt(252) if (returns < 0).any() else 0
            metrics['win_rate'] = (returns > 0).mean()
            metrics['profit_loss_ratio'] = abs(returns[returns > 0].mean() / returns[returns < 0].mean()) if (returns < 0).any() else 0
            metrics['skewness'] = returns.skew()
            metrics['kurtosis'] = returns.kurtosis()
            
            self.strategy_metrics[strategy_name] = metrics
        
        return self.strategy_metrics
    
    def calculate_composite_score(self) -> Dict[str, float]:
        """计算综合评分（多指标加权）"""
        self.composite_scores = {}
        
        weights = {
            'sharpe_ratio': 0.30,
            'calmar_ratio': 0.25,
            'total_return_pct': 0.15,
            'win_rate': 0.10,
            'profit_loss_ratio': 0.10,
            'sortino_ratio': 0.10
        }
        
        for strategy_name, metrics in self.strategy_metrics.items():
            score = 0.0
            
            if 'sharpe_ratio' in metrics:
                sharpe_score = max(0, min(100, (metrics['sharpe_ratio'] + 1) * 33.33))
                score += sharpe_score * weights['sharpe_ratio']
            
            if 'calmar_ratio' in metrics:
                calmar_score = max(0, min(100, metrics['calmar_ratio'] * 20))
                score += calmar_score * weights['calmar_ratio']
            
            if 'total_return_pct' in metrics:
                return_score = max(0, min(100, (metrics['total_return_pct'] + 20) * 1.25))
                score += return_score * weights['total_return_pct']
            
            if 'win_rate' in metrics:
                win_score = max(0, min(100, metrics['win_rate'] * 100))
                score += win_score * weights['win_rate']
            
            if 'profit_loss_ratio' in metrics:
                pl_score = max(0, min(100, metrics['profit_loss_ratio'] * 33.33))
                score += pl_score * weights['profit_loss_ratio']
            
            self.composite_scores[strategy_name] = score
        
        return self.composite_scores
    
    def analyze_strategy_distribution(self) -> Dict:
        """分析策略表现分布"""
        sharpe_values = [m['sharpe_ratio'] for m in self.strategy_metrics.values()]
        return_values = [m['total_return_pct'] for m in self.strategy_metrics.values()]
        drawdown_values = [m['max_drawdown_pct'] for m in self.strategy_metrics.values()]
        
        distribution = {
            'sharpe': {
                'mean': np.mean(sharpe_values),
                'std': np.std(sharpe_values),
                'median': np.median(sharpe_values),
                'p25': np.percentile(sharpe_values, 25),
                'p75': np.percentile(sharpe_values, 75),
                'min': min(sharpe_values),
                'max': max(sharpe_values)
            },
            'return': {
                'mean': np.mean(return_values),
                'std': np.std(return_values),
                'median': np.median(return_values),
                'p25': np.percentile(return_values, 25),
                'p75': np.percentile(return_values, 75),
                'min': min(return_values),
                'max': max(return_values)
            },
            'drawdown': {
                'mean': np.mean(drawdown_values),
                'std': np.std(drawdown_values),
                'median': np.median(drawdown_values),
                'p25': np.percentile(drawdown_values, 25),
                'p75': np.percentile(drawdown_values, 75),
                'min': min(drawdown_values),
                'max': max(drawdown_values)
            }
        }
        
        return distribution
    
    def get_auto_elimination_thresholds(self, distribution: Dict) -> Dict:
        """获取自动淘汰阈值"""
        thresholds = {
            'sharpe_ratio_threshold': distribution['sharpe']['p25'],
            'return_threshold': distribution['return']['p25'],
            'drawdown_threshold': distribution['drawdown']['p75']
        }
        return thresholds
    
    def run_evolution_cycle(self, auto_update_config: bool = True):
        """运行完整进化周期"""
        self.logger.info("="*80)
        self.logger.info("策略进化系统 - 开始")
        self.logger.info("="*80)
        
        # 1. 加载数据
        strategy_values, strategy_returns = self.load_strategy_data()
        
        if not strategy_values:
            self.logger.error("未找到策略数据")
            return [], []
        
        # 2. 计算综合指标
        self.logger.info("\n--- [1/6] 计算综合指标 ---")
        metrics = self.calculate_comprehensive_metrics(strategy_values, strategy_returns)
        
        # 3. 综合评分
        self.logger.info("\n--- [2/6] 综合评分 ---")
        composite_scores = self.calculate_composite_score()
        
        # 4. 分布分析
        self.logger.info("\n--- [3/6] 策略表现分布分析 ---")
        distribution = self.analyze_strategy_distribution()
        
        self.logger.info(f"  夏普比率: 平均={distribution['sharpe']['mean']:.3f}, "
                       f"25%分位={distribution['sharpe']['p25']:.3f}")
        self.logger.info(f"  收益率: 平均={distribution['return']['mean']:.2f}%, "
                       f"25%分位={distribution['return']['p25']:.2f}%")
        self.logger.info(f"  最大回撤: 平均={distribution['drawdown']['mean']:.2f}%, "
                       f"75%分位={distribution['drawdown']['p75']:.2f}%")
        
        # 5. 自动淘汰阈值
        self.logger.info("\n--- [4/6] 自动淘汰阈值 ---")
        thresholds = self.get_auto_elimination_thresholds(distribution)
        
        self.logger.info(f"  夏普比率淘汰线: {thresholds['sharpe_ratio_threshold']:.3f}")
        self.logger.info(f"  收益率淘汰线: {thresholds['return_threshold']:.2f}%")
        self.logger.info(f"  最大回撤淘汰线: {thresholds['drawdown_threshold']:.2f}%")
        
        # 6. 策略筛选
        self.logger.info("\n--- [5/6] 策略筛选决策 ---")
        
        keep_strategies = []
        eliminate_strategies = []
        
        for strategy_name, m in metrics.items():
            keep = True
            
            if m['sharpe_ratio'] < thresholds['sharpe_ratio_threshold']:
                keep = False
            if m['total_return_pct'] < thresholds['return_threshold']:
                keep = False
            if m['max_drawdown_pct'] < thresholds['drawdown_threshold']:
                keep = False
            
            if keep:
                keep_strategies.append(strategy_name)
            else:
                eliminate_strategies.append(strategy_name)
        
        keep_strategies.sort(key=lambda x: composite_scores[x], reverse=True)
        
        if len(keep_strategies) < 8:
            candidates = [s for s in eliminate_strategies 
                         if metrics[s]['sharpe_ratio'] > thresholds['sharpe_ratio_threshold'] * 0.8]
            candidates.sort(key=lambda x: composite_scores[x], reverse=True)
            keep_strategies += candidates[:8-len(keep_strategies)]
            eliminate_strategies = [s for s in eliminate_strategies if s not in keep_strategies]
        
        if len(keep_strategies) > 15:
            keep_strategies = keep_strategies[:15]
        
        self.logger.info(f"  保留策略 ({len(keep_strategies)} 个):")
        for i, s in enumerate(keep_strategies, 1):
            score = composite_scores[s]
            m = metrics[s]
            self.logger.info(f"    {i:2d}. {s:15} "
                           f"| 综合评分: {score:5.1f} "
                           f"| 夏普: {m['sharpe_ratio']:5.3f} "
                           f"| 收益: {m['total_return_pct']:6.2f}% "
                           f"| 回撤: {m['max_drawdown_pct']:6.2f}%")
        
        self.logger.info(f"\n  淘汰策略 ({len(eliminate_strategies)} 个):")
        for i, s in enumerate(eliminate_strategies, 1):
            m = metrics[s]
            self.logger.info(f"    {i:2d}. {s:15} "
                           f"| 夏普: {m['sharpe_ratio']:5.3f} "
                           f"| 收益: {m['total_return_pct']:6.2f}% "
                           f"| 回撤: {m['max_drawdown_pct']:6.2f}%")
        
        # 7. 保存结果
        self.logger.info("\n--- [6/6] 保存结果 ---")
        self._save_evolution_report(metrics, composite_scores, distribution, 
                                      thresholds, keep_strategies, eliminate_strategies)
        
        # 8. 显示更新建议（不再自动修改 config.py）
        if auto_update_config:
            self.logger.info("\n--- config.py 更新建议 ---")
            self.logger.info(f"  建议在 config.py 中保留以下策略:")
            for i, s in enumerate(keep_strategies, 1):
                self.logger.info(f"    {i:2d}. {s}")
            self.logger.info(f"\n  建议移除以下策略:")
            for i, s in enumerate(eliminate_strategies, 1):
                self.logger.info(f"    {i:2d}. {s}")
            self.logger.info(f"\n  请手动修改 config/best_strategy_params.json 文件")
        
        self.logger.info("="*80)
        self.logger.info("✅ 策略进化系统完成！")
        self.logger.info("="*80)
        
        return keep_strategies, eliminate_strategies
    
    def _save_evolution_report(self, metrics, composite_scores, distribution, 
                               thresholds, keep_strategies, eliminate_strategies):
        """保存进化报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        report = {
            'version': 'unified',
            'timestamp': timestamp,
            'distribution': distribution,
            'thresholds': thresholds,
            'strategy_metrics': {},
            'composite_scores': composite_scores,
            'keep_strategies': keep_strategies,
            'eliminate_strategies': eliminate_strategies
        }
        
        for name, m in metrics.items():
            report['strategy_metrics'][name] = {
                'total_return_pct': float(m['total_return_pct']),
                'max_drawdown_pct': float(m['max_drawdown_pct']),
                'sharpe_ratio': float(m['sharpe_ratio']),
                'calmar_ratio': float(m['calmar_ratio']),
                'win_rate': float(m.get('win_rate', 0)),
                'profit_loss_ratio': float(m.get('profit_loss_ratio', 0))
            }
        
        report_path = Config.REPORTS_DIR / f"phase2/evolution_{timestamp}.json"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"  进化报告已保存: {report_path}")
        
        latest_path = Config.REPORTS_DIR / "phase2/evolution_latest.json"
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    
    def _suggest_config_update(self, keep_strategies, eliminate_strategies):
        """
        建议如何更新配置文件（不再自动修改）

        参数:
            keep_strategies: 建议保留的策略列表
            eliminate_strategies: 建议移除的策略列表
        """
        self.logger.info(f"\n  💡 配置更新建议:")
        self.logger.info(f"     请手动编辑 config/best_strategy_params.json")
        self.logger.info(f"     保留策略: {keep_strategies}")
        self.logger.info(f"     移除策略: {eliminate_strategies}")


if __name__ == '__main__':
    print("="*80)
    print("策略进化系统 - 统一版")
    print("="*80)
    print("\n功能：")
    print("  - 多指标综合评分（夏普30% + 卡尔马25% + 收益15% + 胜率10% + 盈亏比10%）")
    print("  - 统计分布分析（25%/75%分位数自动阈值）")
    print("  - 策略稳定性评估（波动率、下行风险、偏度、峰度）")
    print("  - 提供配置更新建议（不再自动修改源代码）")
    print("\n使用：")
    print("  from strategy.strategy_evolution import StrategyEvolutionSystem")
    print("  evolution = StrategyEvolutionSystem()")
    print("  keep, eliminate = evolution.run_evolution_cycle(auto_update_config=True)")
    print("\n" + "="*80)
