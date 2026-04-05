# -*- coding: utf-8 -*-
"""
组合策略模块
提供多策略组合、仓位分配、策略轮动功能
"""
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class StrategyConfig:
    """策略配置"""
    name: str
    params: dict
    weight: float = 0.0
    enabled: bool = True


class PortfolioStrategy:
    """组合策略管理类"""
    
    def __init__(
        self,
        strategy_configs: List[StrategyConfig],
        allocation_method: str = 'equal',
        max_single_weight: float = 0.4,
        min_single_weight: float = 0.05
    ):
        """
        初始化组合策略
        
        参数:
            strategy_configs: 策略配置列表
            allocation_method: 分配方式 ('equal', 'sharpe', 'risk_parity')
            max_single_weight: 单策略最大权重
            min_single_weight: 单策略最小权重
        """
        self.strategy_configs = strategy_configs
        self.allocation_method = allocation_method
        self.max_single_weight = max_single_weight
        self.min_single_weight = min_single_weight
        
        # 性能历史
        self.performance_history = {
            s.name: {'returns': [], 'sharpe': None, 'max_drawdown': None}
            for s in strategy_configs
        }
        
        # 计算初始权重
        self.weights = self._calculate_weights()
    
    def _calculate_weights(self) -> Dict[str, float]:
        """
        计算仓位权重
        
        返回:
            {strategy_name: weight}
        """
        if self.allocation_method == 'equal':
            return self._equal_weighted()
        elif self.allocation_method == 'sharpe':
            return self._sharpe_weighted()
        elif self.allocation_method == 'risk_parity':
            return self._risk_parity()
        else:
            return self._equal_weighted()
    
    def _equal_weighted(self) -> Dict[str, float]:
        """等权重分配"""
        enabled_strategies = [s for s in self.strategy_configs if s.enabled]
        weight = 1.0 / len(enabled_strategies) if enabled_strategies else 0
        
        weights = {}
        for s in self.strategy_configs:
            weights[s.name] = weight if s.enabled else 0.0
        
        return self._normalize_weights(weights)
    
    def _sharpe_weighted(self) -> Dict[str, float]:
        """夏普比率加权"""
        weights = {}
        total_sharpe = 0.0
        
        for s in self.strategy_configs:
            if not s.enabled:
                weights[s.name] = 0.0
                continue
            
            sharpe = self.performance_history[s.name]['sharpe']
            if sharpe is None or sharpe <= 0:
                weights[s.name] = 0.0
            else:
                weights[s.name] = sharpe
                total_sharpe += sharpe
        
        if total_sharpe > 0:
            for s in self.strategy_configs:
                if weights[s.name] > 0:
                    weights[s.name] /= total_sharpe
        
        return self._normalize_weights(weights)
    
    def _risk_parity(self) -> Dict[str, float]:
        """风险平价分配"""
        weights = {}
        total_inv_vol = 0.0
        
        for s in self.strategy_configs:
            if not s.enabled:
                weights[s.name] = 0.0
                continue
            
            returns = self.performance_history[s.name]['returns']
            if len(returns) < 20:
                # 数据不足，等权
                weights[s.name] = 1.0
            else:
                volatility = np.std(returns) * np.sqrt(252)
                if volatility <= 0:
                    weights[s.name] = 1.0
                else:
                    weights[s.name] = 1.0 / volatility
            
            total_inv_vol += weights[s.name]
        
        if total_inv_vol > 0:
            for s in self.strategy_configs:
                if weights[s.name] > 0:
                    weights[s.name] /= total_inv_vol
        
        return self._normalize_weights(weights)
    
    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        归一化权重，限制单策略权重范围
        
        参数:
            weights: 原始权重
            
        返回:
            归一化后的权重
        """
        # 限制单策略权重范围
        for name in weights:
            if weights[name] > 0:
                weights[name] = max(self.min_single_weight, 
                                    min(self.max_single_weight, weights[name]))
        
        # 重新归一化
        total = sum(weights.values())
        if total > 0:
            for name in weights:
                weights[name] /= total
        
        return weights
    
    def update_performance(self, strategy_name: str, returns: List[float], 
                          sharpe: float = None, max_drawdown: float = None):
        """
        更新策略性能数据
        
        参数:
            strategy_name: 策略名称
            returns: 收益率序列
            sharpe: 夏普比率
            max_drawdown: 最大回撤
        """
        if strategy_name in self.performance_history:
            self.performance_history[strategy_name]['returns'] = returns
            self.performance_history[strategy_name]['sharpe'] = sharpe
            self.performance_history[strategy_name]['max_drawdown'] = max_drawdown
    
    def rebalance(self, force: bool = False):
        """
        再平衡仓位
        
        参数:
            force: 是否强制再平衡
        """
        self.weights = self._calculate_weights()
        return self.weights
    
    def get_weights(self) -> Dict[str, float]:
        """获取当前权重"""
        return self.weights
    
    def get_enabled_strategies(self) -> List[str]:
        """获取启用的策略列表"""
        return [s.name for s in self.strategy_configs if s.enabled]
    
    def disable_strategy(self, strategy_name: str):
        """禁用策略"""
        for s in self.strategy_configs:
            if s.name == strategy_name:
                s.enabled = False
                break
        self.weights = self._calculate_weights()
    
    def enable_strategy(self, strategy_name: str):
        """启用策略"""
        for s in self.strategy_configs:
            if s.name == strategy_name:
                s.enabled = True
                break
        self.weights = self._calculate_weights()


# ========== 预设组合方案 ==========

def create_balanced_portfolio() -> PortfolioStrategy:
    """
    创建均衡组合
    
    策略: rsi, mean_reversion, bollinger, volume_spread (各25%)
    """
    from config import Config
    
    strategy_configs = [
        StrategyConfig(
            name='rsi',
            params=Config.get_optimized_params('rsi')
        ),
        StrategyConfig(
            name='mean_reversion',
            params=Config.get_optimized_params('mean_reversion')
        ),
        StrategyConfig(
            name='bollinger',
            params=Config.get_optimized_params('bollinger')
        ),
        StrategyConfig(
            name='volume_spread',
            params=Config.get_optimized_params('volume_spread')
        )
    ]
    
    return PortfolioStrategy(
        strategy_configs=strategy_configs,
        allocation_method='equal'
    )


def create_aggressive_portfolio() -> PortfolioStrategy:
    """
    创建进取组合
    
    策略: ema_cross (30%), sar (20%), rsi (25%), momentum (25%)
    """
    from config import Config
    
    strategy_configs = [
        StrategyConfig(
            name='ema_cross',
            params=Config.get_optimized_params('ema_cross'),
            weight=0.30
        ),
        StrategyConfig(
            name='sar',
            params=Config.get_optimized_params('sar'),
            weight=0.20
        ),
        StrategyConfig(
            name='rsi',
            params=Config.get_optimized_params('rsi'),
            weight=0.25
        ),
        StrategyConfig(
            name='momentum',
            params=Config.get_optimized_params('momentum'),
            weight=0.25
        )
    ]
    
    return PortfolioStrategy(
        strategy_configs=strategy_configs,
        allocation_method='equal'
    )


def create_conservative_portfolio() -> PortfolioStrategy:
    """
    创建保守组合
    
    策略: mean_reversion (30%), cci (25%), keltner (25%), turtle_trading (20%)
    """
    from config import Config
    
    strategy_configs = [
        StrategyConfig(
            name='mean_reversion',
            params=Config.get_optimized_params('mean_reversion'),
            weight=0.30
        ),
        StrategyConfig(
            name='cci',
            params=Config.get_optimized_params('cci'),
            weight=0.25
        ),
        StrategyConfig(
            name='keltner',
            params=Config.get_optimized_params('keltner'),
            weight=0.25
        ),
        StrategyConfig(
            name='turtle_trading',
            params=Config.get_optimized_params('turtle_trading'),
            weight=0.20
        )
    ]
    
    return PortfolioStrategy(
        strategy_configs=strategy_configs,
        allocation_method='equal'
    )


if __name__ == '__main__':
    print("="*80)
    print("组合策略模块")
    print("="*80)
    print("\n可用组合:")
    print("  1. create_balanced_portfolio()     - 均衡组合")
    print("  2. create_aggressive_portfolio()   - 进取组合")
    print("  3. create_conservative_portfolio() - 保守组合")
    print("\n" + "="*80)
