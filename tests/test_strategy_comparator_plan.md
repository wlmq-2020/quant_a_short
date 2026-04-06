# 量化回测系统单元测试方案

## 1. StrategyComparator.run_all_strategies_backtest() 单元测试

## 1. 测试目标

验证 `StrategyComparator.run_all_strategies_backtest()` 函数的正确性，包括：
- 输入参数处理
- 并发执行逻辑
- 结果收集和返回格式
- 错误处理
- 时间记录

## 2. 函数分析

### 函数签名
```python
def run_all_strategies_backtest(self, stock_data, strategy_types=None)
```

### 输入参数
| 参数 | 类型 | 说明 |
|-----|------|------|
| `stock_data` | dict | 股票数据字典 `{stock_code: DataFrame}` |
| `strategy_types` | list or None | 策略类型列表，None 表示使用所有策略 |

### 返回值
```python
{
    'results': {
        'strategy_type': {
            'stock_code': {
                'metrics': {...},
                ...
            }
        }
    },
    'timings': {
        'strategy_timings': {
            'strategy_type': {
                'start_time': datetime,
                'end_time': datetime,
                'duration': timedelta
            }
        },
        'overall_start_time': datetime,
        'overall_end_time': datetime,
        'overall_duration': timedelta
    }
}
```

### 关键依赖
- `run_single_strategy_process()` - 进程入口函数
- `ProcessPoolExecutor` - 进程池
- `get_all_strategy_types()` - 获取所有策略类型

---

## 3. 测试用例设计

### 测试用例 1: 基本功能测试 - 使用 mock 数据
**目标**: 验证函数能正常处理输入并返回正确格式

**准备**:
- Mock `stock_data` - 1-2只股票的简化 DataFrame
- Mock `strategy_types` - ['rsi', 'macd_kdj']
- Patch `ProcessPoolExecutor` - 不实际启动进程
- Patch `run_single_strategy_process` - 返回 mock 结果

**验证**:
- 返回值包含 'results' 和 'timings' 键
- 'results' 包含所有测试的策略
- 'timings' 包含时间信息
- 整体耗时 > 0

---

### 测试用例 2: strategy_types = None（默认所有策略）
**目标**: 验证当 strategy_types 为 None 时，使用 get_all_strategy_types()

**准备**:
- Mock `get_all_strategy_types()` - 返回 ['rsi', 'macd']
- 调用时不传 strategy_types

**验证**:
- `get_all_strategy_types()` 被调用
- 所有返回的策略都被执行

---

### 测试用例 3: 空策略列表
**目标**: 验证传入空策略列表时的行为

**输入**:
- `strategy_types = []`

**验证**:
- 返回空的 results
- 不启动任何进程
- 不抛出异常

---

### 测试用例 4: 空股票数据
**目标**: 验证空股票数据的处理

**输入**:
- `stock_data = {}`

**验证**:
- 每个策略返回空结果
- 函数不崩溃
- 正确记录时间

---

### 测试用例 5: 单个策略失败
**目标**: 验证某个策略失败时，其他策略仍能继续

**准备**:
- Mock 2个策略
- 第1个策略抛出异常
- 第2个策略返回正常结果

**验证**:
- 失败策略有错误日志
- 成功策略结果被收集
- 函数不崩溃，继续执行

---

### 测试用例 6: 配置字典生成
**目标**: 验证 config_dict 正确生成

**验证**:
- 只有非私有、非可调用属性被包含
- 正确传递给进程池

---

### 测试用例 7: 时间记录验证
**目标**: 验证时间信息正确记录

**验证**:
- overall_start_time < overall_end_time
- 每个策略的 start_time < end_time
- duration 计算正确

---

### 测试用例 8: 真实数据集成测试（可选）
**目标**: 使用真实但简化的数据运行

**准备**:
- 加载1-2只真实股票的少量数据
- 使用1-2个策略

**验证**:
- 函数完整执行
- 返回真实的回测结果
- 结果格式正确

---

## 4. Mock 策略

### 需要 mock 的对象
| 对象 | Mock 方式 |
|------|----------|
| `ProcessPoolExecutor` | 返回 mock Future 对象 |
| `run_single_strategy_process` | 返回预定义的结果 |
| `get_all_strategy_types` | 返回测试策略列表 |
| `self.logger` | mock logger 验证日志调用 |
| `print` | 捕获标准输出 |

### Mock 结果数据示例
```python
mock_result = {
    'strategy_type': 'rsi',
    'results': {
        'sh600519': {
            'metrics': {
                'total_return_pct': 10.5,
                'sharpe_ratio': 0.8,
                'win_rate': 60.0,
                'max_drawdown_pct': 5.0,
                'total_trades': 10
            }
        }
    },
    'start_time': datetime(2026, 4, 6, 10, 0, 0),
    'end_time': datetime(2026, 4, 6, 10, 0, 5),
    'duration': timedelta(seconds=5)
}
```

---

## 5. 测试文件结构

```
tests/
├── __init__.py
└── backtest/
    ├── __init__.py
    └── test_strategy_comparator.py
```

---

## 6. 测试实现大纲

### 6.1 基础测试类
```python
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from backtest.backtester import StrategyComparator
```

### 6.2 辅助函数
```python
def create_mock_stock_data(n_stocks=2, n_days=100):
    """创建模拟股票数据"""
    ...

def create_mock_strategy_result(strategy_type, stock_codes):
    """创建模拟策略结果"""
    ...
```

### 6.3 测试类
```python
class TestStrategyComparator(unittest.TestCase):

    def setUp(self):
        """测试前准备"""
        self.config = MagicMock()
        self.logger = MagicMock()
        self.comparator = StrategyComparator(self.config, self.logger)

    @patch('backtest.backtester.ProcessPoolExecutor')
    @patch('backtest.backtester.run_single_strategy_process')
    def test_basic_functionality(self, mock_run_process, mock_executor):
        """测试用例 1: 基本功能"""
        ...

    @patch('strategy.strategy.get_all_strategy_types')
    def test_strategy_types_none(self, mock_get_all):
        """测试用例 2: strategy_types = None"""
        ...

    def test_empty_strategy_list(self):
        """测试用例 3: 空策略列表"""
        ...

    def test_empty_stock_data(self):
        """测试用例 4: 空股票数据"""
        ...

    @patch('backtest.backtester.ProcessPoolExecutor')
    def test_single_strategy_failure(self, mock_executor):
        """测试用例 5: 单个策略失败"""
        ...
```

---

## 7. 断言检查清单

### 通用断言
- [ ] 返回值不是 None
- [ ] 返回值是 dict 类型
- [ ] 包含 'results' 键
- [ ] 包含 'timings' 键

### Results 断言
- [ ] results 是 dict 类型
- [ ] 每个策略类型对应结果
- [ ] 每个结果包含股票数据

### Timings 断言
- [ ] timings 包含 'strategy_timings'
- [ ] timings 包含 'overall_start_time'
- [ ] timings 包含 'overall_end_time'
- [ ] timings 包含 'overall_duration'
- [ ] overall_duration > 0

### 日志断言
- [ ] 成功策略有 info 日志
- [ ] 失败策略有 warning 日志

---

## 8. 测试数据准备

### 模拟 DataFrame 格式
```python
mock_df = pd.DataFrame({
    'date': pd.date_range('2023-01-01', periods=100),
    'open': np.random.uniform(100, 200, 100),
    'high': np.random.uniform(100, 200, 100),
    'low': np.random.uniform(100, 200, 100),
    'close': np.random.uniform(100, 200, 100),
    'volume': np.random.uniform(1000000, 10000000, 100)
})
```

---

## 9. 测试执行顺序

1. 基本功能测试
2. 参数边界测试（None、空列表）
3. 错误处理测试
4. 时间记录测试
5. 集成测试（可选）

---

---

## 11. _update_each_strategy_best_params() 单元测试

### 11.1 测试目标
验证最优参数持久化逻辑的正确性，确保"新高数据覆盖次高数据"：
- 历史为空时新增策略数据
- 本次收益 > 历史收益时更新数据
- 本次收益 ≤ 历史收益时保持历史数据
- None 值处理正确
- JSON 文件读写正确

### 11.2 函数分析
**文件**: `backtest/optimizer.py:448-700+`

**核心逻辑**:
```python
# 辅助函数：处理 None 值的比较
def get_effective_return(val):
    return val if val is not None else -float('inf')

eff_current_return = get_effective_return(current_return)
eff_hist_return = get_effective_return(hist_return)

# 如果本次收益更高，或者历史是None但本次有值，更新历史最优
if eff_current_return > eff_hist_return:
    # 更新数据
elif strategy_type not in historical_best:
    # 新增数据
else:
    # 保持历史
```

**输入**: `optimized_results` - 优化结果字典
```python
{
    'strategy_type': {
        'best_result': {
            'avg_return': float or None,
            'avg_sharpe': float,
            'max_return': float,
            'min_return': float,
            'best_stock': str,
            'worst_stock': str
        },
        'best_params': {...}
    }
}
```

**输出**: 更新 `config/best_strategy_params.json`

---

### 11.3 测试用例设计

#### 测试用例 1: 历史文件不存在 - 全新初始化
**目标**: 验证历史文件不存在时，能正确创建并写入所有策略数据

**准备**:
- Mock `best_params_file.exists()` 返回 False
- 传入 2-3 个策略的优化结果

**验证**:
- JSON 文件被创建
- 所有策略数据都被写入
- 每个策略都有 `updated_at` 时间戳
- `status` 显示 "✓ 新增"

---

#### 测试用例 2: 历史为空，本次有收益 - 新增策略
**目标**: 验证历史为空但本次有收益时，正确新增数据

**输入**:
```python
historical_best = {}
optimized_results = {
    'rsi': {
        'best_result': {
            'avg_return': 15.5,
            'avg_sharpe': 0.8,
            'max_return': 25.0,
            'min_return': 5.0,
            'best_stock': 'sh600519',
            'worst_stock': 'sh600036'
        },
        'best_params': {'rsi_period': 14, ...}
    }
}
```

**验证**:
- `historical_best['rsi']` 被创建
- `avg_return` = 15.5
- `updated_count` = 1
- 日志包含 "新增策略 rsi"

---

#### 测试用例 3: 本次收益 > 历史收益 - 更新数据（核心场景）
**目标**: 验证新高数据正确覆盖次高数据

**输入**:
```python
historical_best = {
    'rsi': {
        'avg_return': 10.0,
        'avg_sharpe': 0.6,
        'best_params': {'rsi_period': 7},
        'updated_at': '2026-04-01 10:00:00'
    }
}
optimized_results = {
    'rsi': {
        'best_result': {
            'avg_return': 15.5,  # 更高！
            'avg_sharpe': 0.8,
            'max_return': 25.0,
            'min_return': 5.0,
            'best_stock': 'sh600519',
            'worst_stock': 'sh600036'
        },
        'best_params': {'rsi_period': 14}  # 新参数
    }
}
```

**验证**:
- `historical_best['rsi']['avg_return']` = 15.5 (更新后)
- `historical_best['rsi']['best_params']` = 新参数
- `updated_count` = 1
- `status` 显示 "↑ 更新!"
- 日志包含 "策略 rsi 提升: 历史 +10.00% → 本次 +15.50%"
- `updated_at` 时间戳更新

---

#### 测试用例 4: 本次收益 < 历史收益 - 保持历史（核心场景）
**目标**: 验证次高数据不覆盖新高数据

**输入**:
```python
historical_best = {
    'rsi': {
        'avg_return': 15.5,  # 历史更高
        'avg_sharpe': 0.8,
        'best_params': {'rsi_period': 14},
        'updated_at': '2026-04-01 10:00:00'
    }
}
optimized_results = {
    'rsi': {
        'best_result': {
            'avg_return': 10.0,  # 本次更低
            'avg_sharpe': 0.6,
            ...
        },
        'best_params': {'rsi_period': 7}
    }
}
```

**验证**:
- `historical_best['rsi']['avg_return']` 保持 15.5
- `historical_best['rsi']['best_params']` 保持旧参数
- `updated_count` = 0
- `status` 显示 "保持历史"
- `updated_at` 时间戳不变

---

#### 测试用例 5: 本次收益 == 历史收益 - 保持历史
**目标**: 验证收益相等时不更新

**输入**:
```python
historical_best = {
    'rsi': {'avg_return': 10.0, 'updated_at': '2026-04-01 10:00:00'}
}
optimized_results = {
    'rsi': {
        'best_result': {'avg_return': 10.0, ...},
        'best_params': {...}
    }
}
```

**验证**:
- 保持历史数据不变
- `updated_count` = 0
- `status` 显示 "保持历史"

---

#### 测试用例 6: 历史收益是 None，本次有收益 - 更新
**目标**: 验证 None 值处理 - 历史为 None 时更新

**输入**:
```python
historical_best = {
    'rsi': {'avg_return': None, 'updated_at': '2026-04-01 10:00:00'}
}
optimized_results = {
    'rsi': {
        'best_result': {'avg_return': 10.0, ...},
        'best_params': {...}
    }
}
```

**验证**:
- `historical_best['rsi']['avg_return']` = 10.0
- `updated_count` = 1
- 日志包含 "策略 rsi 提升"

---

#### 测试用例 7: 历史有收益，本次是 None - 保持历史
**目标**: 验证 None 值处理 - 本次为 None 时不更新

**输入**:
```python
historical_best = {
    'rsi': {'avg_return': 10.0, ...}
}
optimized_results = {
    'rsi': {
        'best_result': {'avg_return': None, ...},
        'best_params': {...}
    }
}
```

**验证**:
- 保持历史收益 10.0
- `updated_count` = 0
- 日志包含 "历史 +10.00% → 本次 N/A, 不更新"

---

#### 测试用例 8: 历史和本次都是 None - 保持（不新增）
**目标**: 验证双方都是 None 时的处理

**输入**:
```python
historical_best = {
    'rsi': {'avg_return': None, ...}
}
optimized_results = {
    'rsi': {
        'best_result': {'avg_return': None, ...},
        'best_params': {...}
    }
}
```

**验证**:
- 不更新
- `updated_count` = 0

---

#### 测试用例 9: 历史文件存在，部分策略更新
**目标**: 验证多策略混合场景 - 部分更新，部分保持

**输入**:
```python
historical_best = {
    'rsi': {'avg_return': 10.0},      # 将被更新
    'macd_kdj': {'avg_return': 20.0}, # 将被保持
    # bollinger 不存在，将被新增
}
optimized_results = {
    'rsi': {'best_result': {'avg_return': 15.0}, ...},  # 更高
    'macd_kdj': {'best_result': {'avg_return': 15.0}, ...},  # 更低
    'bollinger': {'best_result': {'avg_return': 12.0}, ...}  # 新增
}
```

**验证**:
- rsi: 更新 (10.0 → 15.0)
- macd_kdj: 保持 (20.0)
- bollinger: 新增
- `updated_count` = 2
- 状态显示正确

---

#### 测试用例 10: JSON 文件写入验证
**目标**: 验证文件写入格式正确

**验证**:
- 文件是 valid JSON
- `ensure_ascii=False`（中文正常显示）
- `indent=2`（格式化缩进）
- 包含所有必需字段:
  - `avg_return`
  - `avg_sharpe`
  - `max_return`
  - `min_return`
  - `best_stock`
  - `worst_stock`
  - `best_params`
  - `updated_at`

---

#### 测试用例 11: 旧文件迁移（temp → config）
**目标**: 验证兼容逻辑 - temp 目录旧文件迁移到 config 目录

**准备**:
- `temp/best_strategy_params.json` 存在
- `config/best_strategy_params.json` 不存在

**验证**:
- 文件被移动到 config 目录
- temp 目录的文件被删除
- 日志显示迁移成功

---

#### 测试用例 12: 全局最优策略更新到 config.py
**目标**: 验证全局最优策略正确更新 config.py

**准备**:
- Mock config.py 内容
- 历史最优包含多个策略，其中 `rsi` 收益率最高

**验证**:
- `STRATEGY_TYPE` 被更新为 `rsi`
- 对应参数（如 `RSI_PERIOD` 等）被更新
- 日志显示更新的参数

---

### 11.4 Mock 策略

#### 需要 mock 的对象
| 对象 | Mock 方式 |
|------|----------|
| `best_params_file.exists()` | 返回 True/False |
| `open()` | mock_open |
| `json.dump()` | 捕获写入内容 |
| `self.logger` | mock logger 验证日志调用 |
| `print` | 捕获标准输出 |
| `config_path.exists()` | 返回 True |

---

### 11.5 测试文件结构

```
tests/
├── __init__.py
└── backtest/
    ├── __init__.py
    ├── test_strategy_comparator.py
    └── test_optimizer_params_update.py  # 新增：专门测试最优参数更新
```

---

### 11.6 测试实现大纲

```python
import unittest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime
import json
from pathlib import Path

from backtest.optimizer import StrategyOptimizer


class TestBestParamsUpdate(unittest.TestCase):
    """测试最优参数更新逻辑 - _update_each_strategy_best_params()"""

    def setUp(self):
        """测试前准备"""
        self.config = MagicMock()
        self.config.CONFIG_DIR = Path('/tmp/test_config')
        self.logger = MagicMock()
        self.optimizer = StrategyOptimizer(self.config, self.logger)
        self.optimizer.temp_dir = Path('/tmp/test_temp')

    def create_mock_result(self, avg_return, sharpe=0.8, params=None):
        """创建模拟优化结果"""
        return {
            'best_result': {
                'avg_return': avg_return,
                'avg_sharpe': sharpe,
                'max_return': avg_return * 1.5 if avg_return else 0,
                'min_return': avg_return * 0.5 if avg_return else 0,
                'best_stock': 'sh600519',
                'worst_stock': 'sh600036'
            },
            'best_params': params or {'param1': 1}
        }

    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_historical_empty_new_strategy(self, mock_exists, mock_file):
        """测试用例 2: 历史为空，新增策略"""
        mock_exists.return_value = False
        
        optimized_results = {
            'rsi': self.create_mock_result(15.5)
        }
        
        self.optimizer._update_each_strategy_best_params(optimized_results)
        
        # 验证文件被写入
        mock_file.assert_called()
        handle = mock_file()
        written_data = json.loads(handle.write.call_args[0][0])
        self.assertIn('rsi', written_data)
        self.assertEqual(written_data['rsi']['avg_return'], 15.5)

    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_higher_return_updates_history(self, mock_exists, mock_file):
        """测试用例 3: 本次收益 > 历史收益 - 更新数据（核心场景）"""
        mock_exists.return_value = True
        
        # Mock 读取历史数据
        historical_data = {
            'rsi': {
                'avg_return': 10.0,
                'avg_sharpe': 0.6,
                'best_params': {'rsi_period': 7},
                'updated_at': '2026-04-01 10:00:00'
            }
        }
        mock_file.return_value.read.return_value = json.dumps(historical_data)
        
        optimized_results = {
            'rsi': self.create_mock_result(15.5, sharpe=0.8, params={'rsi_period': 14})
        }
        
        self.optimizer._update_each_strategy_best_params(optimized_results)
        
        # 验证更新后的数据
        handle = mock_file()
        written_json = handle.write.call_args[0][0]
        written_data = json.loads(written_json)
        self.assertEqual(written_data['rsi']['avg_return'], 15.5)
        self.assertEqual(written_data['rsi']['best_params']['rsi_period'], 14)
        
        # 验证日志
        self.logger.info.assert_called()
        log_msg = self.logger.info.call_args[0][0]
        self.assertIn('提升', log_msg)
        self.assertIn('10.00', log_msg)
        self.assertIn('15.50', log_msg)

    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_lower_return_keeps_history(self, mock_exists, mock_file):
        """测试用例 4: 本次收益 < 历史收益 - 保持历史（核心场景）"""
        mock_exists.return_value = True
        
        historical_data = {
            'rsi': {
                'avg_return': 15.5,
                'avg_sharpe': 0.8,
                'best_params': {'rsi_period': 14},
                'updated_at': '2026-04-01 10:00:00'
            }
        }
        mock_file.return_value.read.return_value = json.dumps(historical_data)
        
        optimized_results = {
            'rsi': self.create_mock_result(10.0, sharpe=0.6, params={'rsi_period': 7})
        }
        
        self.optimizer._update_each_strategy_best_params(optimized_results)
        
        # 验证保持历史数据
        handle = mock_file()
        # 检查是否有写入调用 - 应该没有更新写入
        # (注意：实际实现总是会重写文件，所以需要检查内容是否保持原样)

    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_none_handling_historical_none(self, mock_exists, mock_file):
        """测试用例 6: 历史收益是 None，本次有收益 - 更新"""
        mock_exists.return_value = True
        
        historical_data = {
            'rsi': {
                'avg_return': None,
                'updated_at': '2026-04-01 10:00:00'
            }
        }
        mock_file.return_value.read.return_value = json.dumps(historical_data)
        
        optimized_results = {
            'rsi': self.create_mock_result(10.0)
        }
        
        self.optimizer._update_each_strategy_best_params(optimized_results)
        
        # 验证更新
        written_json = mock_file().write.call_args[0][0]
        written_data = json.loads(written_json)
        self.assertEqual(written_data['rsi']['avg_return'], 10.0)

    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_none_handling_current_none(self, mock_exists, mock_file):
        """测试用例 7: 历史有收益，本次是 None - 保持历史"""
        mock_exists.return_value = True
        
        historical_data = {
            'rsi': {
                'avg_return': 10.0,
                'updated_at': '2026-04-01 10:00:00'
            }
        }
        mock_file.return_value.read.return_value = json.dumps(historical_data)
        
        optimized_results = {
            'rsi': self.create_mock_result(None)
        }
        
        self.optimizer._update_each_strategy_best_params(optimized_results)
        
        # 验证日志包含 "不更新"
        self.logger.info.assert_called()
        log_msg = self.logger.info.call_args[0][0]
        self.assertIn('不更新', log_msg)

    @patch('builtins.open', new_callable=mock_open)
    @patch('pathlib.Path.exists')
    def test_mixed_strategies_update(self, mock_exists, mock_file):
        """测试用例 9: 多策略混合场景"""
        mock_exists.return_value = True
        
        historical_data = {
            'rsi': {'avg_return': 10.0},
            'macd_kdj': {'avg_return': 20.0}
        }
        mock_file.return_value.read.return_value = json.dumps(historical_data)
        
        optimized_results = {
            'rsi': self.create_mock_result(15.0),      # 更新
            'macd_kdj': self.create_mock_result(15.0),  # 保持
            'bollinger': self.create_mock_result(12.0)  # 新增
        }
        
        self.optimizer._update_each_strategy_best_params(optimized_results)
        
        # 验证结果
        written_json = mock_file().write.call_args[0][0]
        written_data = json.loads(written_json)
        self.assertEqual(written_data['rsi']['avg_return'], 15.0)
        self.assertEqual(written_data['macd_kdj']['avg_return'], 20.0)
        self.assertIn('bollinger', written_data)
```

---

### 11.7 断言检查清单

#### 核心逻辑断言（最重要）
- [ ] **历史为空 + 本次有值 → 新增** ✓
- [ ] **本次收益 > 历史收益 → 更新** ✓（核心）
- [ ] **本次收益 < 历史收益 → 保持** ✓（核心）
- [ ] **本次收益 == 历史收益 → 保持**
- [ ] **历史 None + 本次有值 → 更新**
- [ ] **历史有值 + 本次 None → 保持**
- [ ] **双方都是 None → 保持**

#### 数据完整性断言
- [ ] 每个策略包含 `avg_return`
- [ ] 每个策略包含 `avg_sharpe`
- [ ] 每个策略包含 `max_return` / `min_return`
- [ ] 每个策略包含 `best_stock` / `worst_stock`
- [ ] 每个策略包含 `best_params`
- [ ] 每个策略包含 `updated_at` 时间戳

#### 文件 I/O 断言
- [ ] JSON 文件正确创建/读取
- [ ] 写入内容是 valid JSON
- [ ] 中文正常显示（ensure_ascii=False）
- [ ] 缩进正确（indent=2）

#### 日志断言
- [ ] 新增策略有 "新增策略" 日志
- [ ] 更新策略有 "提升" 日志
- [ ] 不更新策略有 "不更新" 日志

---

## 12. 注意事项

### Windows 多进程问题
- 单元测试尽量避免真实多进程
- 使用 mock 替代 ProcessPoolExecutor

### 数据依赖
- 测试不应依赖外部数据文件
- 使用 mock 或生成的测试数据

### 测试速度
- 单元测试应该快速执行（<1秒）
- 避免实际运行回测

### 可重复性
- 每次测试结果应该一致
- 使用固定随机种子

### 最优参数更新测试优先级
- **最高优先级**: 测试用例 3 和 4（收益比较核心逻辑）
- **高优先级**: 测试用例 2, 6, 7（None 值处理）
- **中优先级**: 测试用例 9, 10, 11（多策略、文件 I/O）
