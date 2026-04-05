# -*- coding: utf-8 -*-
"""
全局配置模块
集中管理所有配置参数
"""
import os
from pathlib import Path
from datetime import datetime, timedelta


class Config:
    """全局配置类"""

    # ========== 项目路径配置 ==========
    # 项目根目录
    PROJECT_ROOT = Path(__file__).parent

    # 各目录路径
    LOG_DIR = PROJECT_ROOT / "logs"
    SAVED_DATA_DIR = PROJECT_ROOT / "saved_data"
    REPORTS_DIR = PROJECT_ROOT / "reports"
    TEMP_DIR = PROJECT_ROOT / "temp"
    CONFIG_DIR = PROJECT_ROOT / "config"

    # ========== 回测时间范围（最近3年） ==========
    # 硬编码日期作为后备
    START_DATE = "20230329"
    END_DATE = "20260329"

    @classmethod
    def get_start_date(cls):
        """获取回测开始日期（3年前）"""
        return (datetime.now() - timedelta(days=3*365)).strftime("%Y%m%d")

    @classmethod
    def get_end_date(cls):
        """获取回测结束日期（昨天）"""
        return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    # ========== 股票配置 ==========
    # 上证50成分股完整列表（50只）
    STOCK_CODES = [
        "sh600519",  # 贵州茅台
        "sh601318",  # 中国平安
        "sh600036",  # 招商银行
        "sh601166",  # 兴业银行
        "sh601288",  # 农业银行
        "sh601988",  # 中国银行
        "sh601398",  # 工商银行
        "sh600000",  # 浦发银行
        "sh600030",  # 中信证券
        "sh600887",  # 伊利股份
        "sh601899",  # 紫金矿业
        "sh601888",  # 中国中免
        "sh601668",  # 中国建筑
        "sh601601",  # 中国太保
        "sh600900",  # 长江电力
        "sh600028",  # 中国石化
        "sh601088",  # 中国神华
        "sh600048",  # 保利发展
        "sh600309",  # 万华化学
        "sh600690",  # 海尔智家
        "sh600585",  # 海螺水泥
        "sh600276",  # 恒瑞医药
        "sh601012",  # 隆基绿能
        "sh601138",  # 工业富联
        "sh601225",  # 陕西煤业
        "sh600111",  # 北方稀土
        "sh600745",  # 闻泰科技
        "sh600547",  # 山东黄金
        "sz000858",  # 五粮液
        "sz000333",  # 美的集团
        "sz002594",  # 比亚迪
        "sz002415",  # 海康威视
        "sz000568",  # 泸州老窖
        "sz000001",  # 平安银行
        "sz000725",  # 京东方A
        "sz002475",  # 立讯精密
        "sz002049",  # 紫光国微
        "sz002241",  # 歌尔股份
        "sz000651",  # 格力电器
        "sz000895",  # 双汇发展
        "sz002352",  # 顺丰控股
        "sz002271",  # 东方雨虹
        "sz002371",  # 北方华创
        "sz002180",  # 纳思达
        "sz002714",  # 牧原股份
        "sz300059",  # 东方财富
        "sz300750",  # 宁德时代
        "sz300122",  # 智飞生物
        "sz300015",  # 爱尔眼科
        "sz300274",  # 阳光电源
    ]

    # 回测时间范围（最近3年）
    START_DATE = "20230329"
    END_DATE = "20260329"

    # K线周期："daily" (日线), "60min" (60分钟线)
    KLINE_PERIOD = "daily"

    # ========== 交易规则配置 ==========
    # 手续费：万分之2.5
    COMMISSION_RATE = 0.00025

    # 印花税：千分之1（仅卖出时收取）
    STAMP_DUTY_RATE = 0.001

    # 过户费：万分之0.2（双向收取）
    TRANSFER_FEE_RATE = 0.00002

    # 最低手续费5元
    MIN_COMMISSION = 5.0

    # 涨跌幅限制：10%
    PRICE_LIMIT = 0.1

    # T+1规则：True表示启用
    T1_RULE = True

    # ========== 策略配置 ==========
    # 策略类型（共18种量化策略）：
    # - "macd_kdj"      : MACD+KDJ共振策略（经典技术指标组合）
    # - "rsi"           : RSI超买超卖策略（相对强弱指标）
    # - "bollinger"     : 布林带突破策略（波动率通道）
    # - "ma_cross"      : 均线交叉策略（简单均线金叉死叉）
    # - "kdj_oversold"  : KDJ超卖超买策略（随机指标）
    # - "macd_zero_axis": MACD零轴策略（多空分界）
    # - "triple_screen" : 三重滤网交易系统（趋势+震荡）
    # - "turtle_trading": 海龟交易策略（经典趋势跟踪）
    # - "momentum"      : 动量策略（追涨杀跌）
    # - "mean_reversion": 均值回归策略（回归中枢）
    # - "donchian"      : 唐奇安通道策略（突破系统）
    # - "williams_r"    : 威廉指标策略（超买超卖）
    # - "cci"           : 顺势指标策略（市场异常）
    # - "ema_cross"     : 指数均线交叉策略（加权平均）
    # - "volume_spread" : 量价配合策略（成交量确认）
    # - "sar"           : 抛物线转向策略（趋势止损）
    # - "keltner"       : 凯特纳通道策略（ATR通道）
    STRATEGY_TYPE = "rsi"

    # MACD参数 (优化后)
    MACD_FAST = 16
    MACD_SLOW = 20
    MACD_SIGNAL = 9

    # KDJ参数 (优化后)
    KDJ_N = 9
    KDJ_M1 = 2
    KDJ_M2 = 3

    # RSI参数 (优化后)
    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30

    # 布林带参数 (优化后)
    BOLLINGER_PERIOD = 20
    BOLLINGER_STD = 2.5

    # 成交量过滤：True表示启用
    VOLUME_FILTER = True
    # 成交量倍数：大于N日均量
    VOLUME_RATIO = 1.5

    # ========== 回测配置 ==========
    # 初始资金
    INITIAL_CAPITAL = 100000.0

    # 每次交易仓位比例（0-1）
    POSITION_RATIO = 0.8

    # 止损比例（0-1）
    STOP_LOSS_RATIO = 0.05

    # 止盈比例（0-1）
    TAKE_PROFIT_RATIO = 0.15

    # ========== 模块开关配置 ==========
    # 注意：所有功能通过 main.py 命令行参数控制
    # 无需在此配置开关

    # ========== 日志配置 ==========
    # 日志级别：DEBUG, INFO, WARNING, ERROR
    LOG_LEVEL = "INFO"

    # 日志文件保留天数
    LOG_RETENTION_DAYS = 7

    @classmethod
    def ensure_dirs(cls):
        """确保所有目录存在"""
        dirs = [
            cls.LOG_DIR,
            cls.SAVED_DATA_DIR,
            cls.REPORTS_DIR,
            cls.TEMP_DIR,
            cls.CONFIG_DIR,
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_best_params_path(cls):
        """获取最优参数文件路径"""
        return cls.CONFIG_DIR / "best_strategy_params.json"

    @classmethod
    def get_stock_list(cls):
        """获取股票代码列表"""
        return cls.STOCK_CODES

    @classmethod
    def is_stock_data_exists(cls, stock_code, period='daily'):
        """检查本地是否已有股票数据"""
        save_path = cls.SAVED_DATA_DIR / f"{stock_code}_{period}.csv"
        return save_path.exists()

    @classmethod
    def calculate_fees(cls, amount, is_sell=False):
        """
        计算交易费用

        参数:
            amount: 交易金额
            is_sell: 是否为卖出

        返回:
            总手续费
        """
        # 手续费
        commission = max(amount * cls.COMMISSION_RATE, cls.MIN_COMMISSION)

        # 过户费（双向）
        transfer_fee = amount * cls.TRANSFER_FEE_RATE

        # 印花税（仅卖出）
        stamp_duty = amount * cls.STAMP_DUTY_RATE if is_sell else 0.0

        return commission + transfer_fee + stamp_duty
