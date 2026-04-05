# -*- coding: utf-8 -*-
"""
统一量化报表模块
负责生成回测汇总 Markdown 报告
"""
from pathlib import Path
from datetime import datetime


class QuantReporter:
    """量化报表类"""

    def __init__(self, config, logger):
        """
        初始化报表生成器

        参数:
            config: 配置对象
            logger: 日志对象
        """
        self.config = config
        self.logger = logger
        self.reports_dir = Path(config.REPORTS_DIR)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_summary_report(self, all_backtest_results, all_paper_results=None):
        """
        生成汇总 Markdown 报告

        参数:
            all_backtest_results: {stock_code: backtest_result}
            all_paper_results: {stock_code: paper_trade_result}

        返回:
            str: 报告文件路径
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.reports_dir / f"summary_report_{timestamp}.md"

        report_lines = []

        # 标题
        report_lines.append("# A股短线量化交易回测汇总报告\n")
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 配置摘要
        report_lines.append("## 配置摘要\n")
        report_lines.append(f"- 回测期间: {self.config.get_start_date()} ~ {self.config.get_end_date()}")
        report_lines.append(f"- 策略类型: {self.config.STRATEGY_TYPE}")
        report_lines.append(f"- 初始资金: {self.config.INITIAL_CAPITAL:.0f} 元")
        report_lines.append(f"- 仓位比例: {self.config.POSITION_RATIO*100:.0f}%")
        report_lines.append(f"- 止损: {self.config.STOP_LOSS_RATIO*100:.1f}%, 止盈: {self.config.TAKE_PROFIT_RATIO*100:.1f}%\n")

        # 汇总表格
        report_lines.append("## 回测结果汇总\n")
        report_lines.append("| 股票代码 | 总收益率 | 年化收益率 | 最大回撤 | 夏普比率 | 胜率 | 交易次数 |")
        report_lines.append("|----------|----------|------------|----------|----------|------|----------|")

        sorted_stocks = sorted(
            all_backtest_results.items(),
            key=lambda x: x[1]['metrics']['total_return_pct'],
            reverse=True
        )

        for stock_code, result in sorted_stocks:
            metrics = result['metrics']
            report_lines.append(
                f"| {stock_code} | "
                f"{metrics['total_return_pct']:+.2f}% | "
                f"{metrics['annual_return_pct']:+.2f}% | "
                f"{metrics['max_drawdown_pct']:.2f}% | "
                f"{metrics['sharpe_ratio']:.3f} | "
                f"{metrics['win_rate']:.2f}% | "
                f"{metrics['total_trades']} |"
            )

        report_lines.append("")

        # 最佳/最差表现
        if sorted_stocks:
            best_code, best_result = sorted_stocks[0]
            worst_code, worst_result = sorted_stocks[-1]

            report_lines.append("## 最佳表现\n")
            report_lines.append(f"- **{best_code}**")
            report_lines.append(f"  - 总收益率: {best_result['metrics']['total_return_pct']:+.2f}%")
            report_lines.append(f"  - 最大回撤: {best_result['metrics']['max_drawdown_pct']:.2f}%")
            report_lines.append(f"  - 胜率: {best_result['metrics']['win_rate']:.2f}%\n")

            if len(sorted_stocks) > 1:
                report_lines.append("## 最差表现\n")
                report_lines.append(f"- **{worst_code}**")
                report_lines.append(f"  - 总收益率: {worst_result['metrics']['total_return_pct']:+.2f}%")
                report_lines.append(f"  - 最大回撤: {worst_result['metrics']['max_drawdown_pct']:.2f}%")
                report_lines.append(f"  - 胜率: {worst_result['metrics']['win_rate']:.2f}%\n")

        # 收益统计
        returns = [r['metrics']['total_return_pct'] for _, r in sorted_stocks]
        if returns:
            avg_return = sum(returns) / len(returns)
            positive_count = sum(1 for r in returns if r > 0)
            report_lines.append("## 收益统计\n")
            report_lines.append(f"- 平均收益率: {avg_return:+.2f}%")
            report_lines.append(f"- 正收益股票数: {positive_count}/{len(returns)}")
            if len(returns) > 1:
                report_lines.append(f"- 最高收益率: {max(returns):+.2f}%")
                report_lines.append(f"- 最低收益率: {min(returns):+.2f}%\n")

        # 写入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        self.logger.info(f"汇总报告已生成: {report_path}")
        return str(report_path)

    def generate_report(self, backtest_result=None, paper_trade_result=None, stock_code=None):
        """
        单个股票报表（保留接口，不做实际生成）
        """
        # 不再生成单个股票的复杂报表
        return {}

    def generate_strategy_comparison_report(self, all_strategy_results):
        """
        生成策略对比报告

        参数:
            all_strategy_results: {strategy_type: {stock_code: backtest_result}}

        返回:
            str: 报告文件路径
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.reports_dir / f"strategy_comparison_{timestamp}.md"

        report_lines = []

        # 标题
        report_lines.append("# 量化策略对比报告\n")
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 配置摘要
        report_lines.append("## 配置摘要\n")
        report_lines.append(f"- 回测期间: {self.config.get_start_date()} ~ {self.config.get_end_date()}")
        report_lines.append(f"- 初始资金: {self.config.INITIAL_CAPITAL:.0f} 元")
        report_lines.append(f"- 仓位比例: {self.config.POSITION_RATIO*100:.0f}%")
        report_lines.append(f"- 止损: {self.config.STOP_LOSS_RATIO*100:.1f}%, 止盈: {self.config.TAKE_PROFIT_RATIO*100:.1f}%\n")

        # 统计每个策略的表现
        strategy_summary = []

        for strategy_type, stock_results in all_strategy_results.items():
            if not stock_results:
                continue

            # 收集所有股票的指标
            returns = []
            annual_returns = []
            max_drawdowns = []
            sharpe_ratios = []
            win_rates = []
            total_trades_list = []
            positive_count = 0

            for stock_code, result in stock_results.items():
                metrics = result['metrics']
                returns.append(metrics['total_return_pct'])
                annual_returns.append(metrics['annual_return_pct'])
                max_drawdowns.append(metrics['max_drawdown_pct'])
                sharpe_ratios.append(metrics['sharpe_ratio'])
                win_rates.append(metrics['win_rate'])
                total_trades_list.append(metrics['total_trades'])
                if metrics['total_return_pct'] > 0:
                    positive_count += 1

            # 计算平均值
            avg_return = sum(returns) / len(returns) if returns else 0
            avg_annual_return = sum(annual_returns) / len(annual_returns) if annual_returns else 0
            avg_max_drawdown = sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0
            avg_sharpe = sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0
            avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0
            avg_trades = sum(total_trades_list) / len(total_trades_list) if total_trades_list else 0
            positive_rate = (positive_count / len(returns) * 100) if returns else 0

            strategy_summary.append({
                'strategy_type': strategy_type,
                'avg_return': avg_return,
                'avg_annual_return': avg_annual_return,
                'avg_max_drawdown': avg_max_drawdown,
                'avg_sharpe': avg_sharpe,
                'avg_win_rate': avg_win_rate,
                'avg_trades': avg_trades,
                'positive_rate': positive_rate,
                'stock_count': len(returns)
            })

        # 按平均收益率从高到低排序
        strategy_summary.sort(key=lambda x: x['avg_return'], reverse=True)

        # 策略对比汇总表
        report_lines.append("## 策略对比汇总（按平均收益率排序）\n")
        report_lines.append("| 排名 | 策略类型 | 平均收益率 | 年化收益率 | 最大回撤 | 夏普比率 | 胜率 | 正收益占比 | 平均交易次数 | 股票数 |")
        report_lines.append("|------|----------|------------|------------|----------|----------|------|------------|--------------|--------|")

        for idx, summary in enumerate(strategy_summary, 1):
            report_lines.append(
                f"| {idx} | {summary['strategy_type']} | "
                f"{summary['avg_return']:+.2f}% | "
                f"{summary['avg_annual_return']:+.2f}% | "
                f"{summary['avg_max_drawdown']:.2f}% | "
                f"{summary['avg_sharpe']:.3f} | "
                f"{summary['avg_win_rate']:.2f}% | "
                f"{summary['positive_rate']:.2f}% | "
                f"{summary['avg_trades']:.1f} | "
                f"{summary['stock_count']} |"
            )

        report_lines.append("")

        # 最佳策略
        if strategy_summary:
            best = strategy_summary[0]
            report_lines.append("## 最佳策略\n")
            report_lines.append(f"- **{best['strategy_type']}**")
            report_lines.append(f"  - 平均收益率: {best['avg_return']:+.2f}%")
            report_lines.append(f"  - 年化收益率: {best['avg_annual_return']:+.2f}%")
            report_lines.append(f"  - 最大回撤: {best['avg_max_drawdown']:.2f}%")
            report_lines.append(f"  - 夏普比率: {best['avg_sharpe']:.3f}")
            report_lines.append(f"  - 胜率: {best['avg_win_rate']:.2f}%")
            report_lines.append(f"  - 正收益占比: {best['positive_rate']:.2f}%")
            report_lines.append(f"  - 平均交易次数: {best['avg_trades']:.1f}")
            report_lines.append(f"  - 测试股票数: {best['stock_count']}\n")

        # 各策略详细表现
        report_lines.append("## 各策略详细表现\n")

        for summary in strategy_summary:
            strategy_type = summary['strategy_type']
            stock_results = all_strategy_results[strategy_type]

            report_lines.append(f"### {strategy_type}\n")
            report_lines.append("| 股票代码 | 总收益率 | 年化收益率 | 最大回撤 | 夏普比率 | 胜率 | 交易次数 |")
            report_lines.append("|----------|----------|------------|----------|----------|------|----------|")

            # 按收益率排序股票
            sorted_stocks = sorted(
                stock_results.items(),
                key=lambda x: x[1]['metrics']['total_return_pct'],
                reverse=True
            )

            for stock_code, result in sorted_stocks:
                metrics = result['metrics']
                report_lines.append(
                    f"| {stock_code} | "
                    f"{metrics['total_return_pct']:+.2f}% | "
                    f"{metrics['annual_return_pct']:+.2f}% | "
                    f"{metrics['max_drawdown_pct']:.2f}% | "
                    f"{metrics['sharpe_ratio']:.3f} | "
                    f"{metrics['win_rate']:.2f}% | "
                    f"{metrics['total_trades']} |"
                )

            report_lines.append("")

        # 写入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        self.logger.info(f"策略对比报告已生成: {report_path}")
        return str(report_path)
