# -*- coding: utf-8 -*-
"""
邮件通知模块
用于发送交易报告、告警信息等邮件
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from datetime import datetime
import traceback


class EmailNotifier:
    """邮件通知器"""

    def __init__(self, config):
        """
        初始化邮件通知器

        参数:
            config: 配置对象，包含邮件相关配置
        """
        self.config = config
        self.enabled = getattr(config, 'EMAIL_NOTIFICATION_ENABLED', False)
        self.smtp_server = getattr(config, 'EMAIL_SMTP_SERVER', 'smtp.qq.com')
        self.smtp_port = getattr(config, 'EMAIL_SMTP_PORT', 465)
        self.sender = getattr(config, 'EMAIL_SENDER', '')
        self.password = getattr(config, 'EMAIL_SENDER_PASSWORD', '')
        self.recipients = getattr(config, 'EMAIL_RECIPIENTS', [])

        # 验证配置
        if self.enabled:
            if not all([self.smtp_server, self.smtp_port, self.sender, self.password, self.recipients]):
                self.enabled = False
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("邮件通知配置不完整，已自动禁用")

    def _send_email(self, subject: str, content: str, success_log_msg: str, error_log_msg: str) -> bool:
        """
        通用邮件发送方法

        参数:
            subject: 邮件主题
            content: 邮件内容
            success_log_msg: 发送成功时的日志信息
            error_log_msg: 发送失败时的日志信息前缀

        返回:
            是否发送成功
        """
        if not self.enabled:
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = ', '.join(self.recipients)
            msg['Subject'] = subject

            msg.attach(MIMEText(content, 'plain', 'utf-8'))

            # 发送邮件
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.recipients, msg.as_string())

            import logging
            logger = logging.getLogger(__name__)
            logger.info(success_log_msg)
            return True

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"{error_log_msg}：{str(e)}", exc_info=True)
            return False

    def send_daily_report(self, report: Dict) -> bool:
        """
        发送每日交易报告邮件

        参数:
            report: 交易报告字典

        返回:
            是否发送成功
        """
        subject = f"【量化模拟盘】{report['trade_date']}交易报告"
        content = self._build_report_content(report)
        return self._send_email(
            subject=subject,
            content=content,
            success_log_msg="交易报告邮件发送成功",
            error_log_msg="发送交易报告邮件失败"
        )

    def send_alert(self, title: str, content: str) -> bool:
        """
        发送告警邮件

        参数:
            title: 告警标题
            content: 告警内容

        返回:
            是否发送成功
        """
        subject = f"【量化模拟盘告警】{title}"
        return self._send_email(
            subject=subject,
            content=content,
            success_log_msg=f"告警邮件发送成功：{title}",
            error_log_msg="发送告警邮件失败"
        )

    def _build_report_content(self, report: Dict) -> str:
        """
        构建报告文本内容

        参数:
            report: 交易报告字典

        返回:
            格式化的报告文本
        """
        content = [
            "=" * 60,
            f"📅 交易日期：{report['trade_date']}",
            f"💹 今日交易：共{report['total_trades']}笔（买入{report['buy_trades']}笔，卖出{report['sell_trades']}笔）",
            f"💰 今日实现盈亏：{report['total_realized_profit']:.2f} 元",
            "",
            "=" * 60,
            "💼 账户信息：",
            f"可用资金：{report['cash']:.2f} 元",
            f"持仓市值：{report['position_value']:.2f} 元",
            f"总资产：{report['total_value']:.2f} 元",
            f"总收益率：{report['total_return_pct']:.2f} %",
            f"持仓数量：{report['position_count']} 只",
            "",
            "=" * 60,
        ]

        if report['positions']:
            content.append("📊 当前持仓：")
            for pos in report['positions']:
                profit_icon = "✅" if pos['unrealized_profit'] >= 0 else "❌"
                content.append(
                    f"{profit_icon} {pos['stock_code']}: {pos['shares']}股，成本价{pos['avg_price']:.2f}，"
                    f"当前价{pos['current_price']:.2f}，浮盈{pos['unrealized_profit']:.2f}元（{pos['unrealized_profit_pct']:.2f}%）"
                )
            content.append("")
        else:
            content.append("📊 当前持仓：空仓")
            content.append("")

        if report['trade_details']:
            content.append("=" * 60)
            content.append("📝 今日交易明细：")
            for trade in report['trade_details']:
                if trade['type'] == 'buy':
                    content.append(
                        f"🔵 买入 {trade['stock_code']}: {trade['shares']}股，价格{trade['price']:.2f}，"
                        f"金额{trade['amount']:.2f}，手续费{trade['fee']:.2f}"
                    )
                else:
                    profit_icon = "✅" if trade['realized_profit'] >= 0 else "❌"
                    content.append(
                        f"🔴 卖出 {trade['stock_code']}: {trade['shares']}股，价格{trade['price']:.2f}，"
                        f"收入{trade['net_income']:.2f}，{profit_icon} 盈亏{trade['realized_profit']:.2f}元（{trade['realized_profit_pct']:.2f}%）"
                    )
            content.append("")

        content.append("=" * 60)
        content.append("🤖 本邮件由量化交易系统自动发送，请勿直接回复")
        content.append("=" * 60)

        return '\n'.join(content)
