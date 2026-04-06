
# -*- coding: utf-8 -*-
"""
快速运行单元测试脚本
使用方法：
    python tests/run_tests.py          # 运行所有测试
    python tests/run_tests.py backtest # 只运行回测测试
    python tests/run_tests.py data     # 只运行数据获取测试
"""
import sys
import unittest
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_tests(test_modules):
    """运行指定的测试模块"""
    print("=" * 80)
    print("运行单元测试")
    print("=" * 80)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for module in test_modules:
        try:
            suite.addTests(loader.loadTestsFromName(module))
        except Exception as e:
            print(f"[ERROR] 加载测试模块失败: {module}")
            print(f"        {e}")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    if result.wasSuccessful():
        print("[OK] 所有测试通过！")
    else:
        print(f"[FAIL] 测试失败：{len(result.failures)} 个失败，{len(result.errors)} 个错误")
    print("=" * 80)

    return result.wasSuccessful()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "backtest":
            run_tests(["tests.test_backtest"])
        elif sys.argv[1] == "data":
            run_tests(["tests.test_data_fetcher"])
        else:
            print("未知参数！")
            print("使用方法:")
            print("  python tests/run_tests.py          # 运行所有测试")
            print("  python tests/run_tests.py backtest # 只运行回测测试")
            print("  python tests/run_tests.py data     # 只运行数据获取测试")
            sys.exit(1)
    else:
        # 默认运行所有测试
        success = run_tests([
            "tests.test_strategy",
            "tests.test_backtest",
            "tests.test_data_fetcher",
            "tests.test_logger",
            "tests.test_config"
        ])
        sys.exit(0 if success else 1)

