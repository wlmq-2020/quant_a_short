# -*- coding: utf-8 -*-
"""
常量配置模块
存放所有静态配置参数，不随运行过程改变
"""
import os
import pytz
from pathlib import Path
from datetime import datetime, timedelta


class ConfigSettings:
    """静态配置类"""

    # ========== 项目基础配置 ==========
    # 时区：统一使用上海时区
    TIMEZONE = pytz.timezone('Asia/Shanghai')

    # 项目根目录（兼容 config.py 在根目录或 config/ 目录的情况）
    _file_path = Path(__file__)
    if _file_path.parent.name == "config":
        PROJECT_ROOT = _file_path.parent.parent
    else:
        PROJECT_ROOT = _file_path.parent

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
        return (datetime.now(cls.TIMEZONE) - timedelta(days=3*365)).strftime("%Y%m%d")

    @classmethod
    def get_end_date(cls):
        """获取回测结束日期（昨天）"""
        return (datetime.now(cls.TIMEZONE) - timedelta(days=1)).strftime("%Y%m%d")

    # ========== 股票配置 ==========
    # 股票代码前缀常量
    STOCK_PREFIX_SH = "sh"
    STOCK_PREFIX_SZ = "sz"

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

    # K线周期："daily" (日线), "60min" (60分钟线)
    KLINE_PERIOD = "daily"

    # ========== 交易规则配置 ==========
    # 手续费：万分之2.5
    COMMISSION_RATE = 0.00025

    # 印花税：千分之1（仅卖出时收取）
    STAMP_DUTY_RATE = 0.001

    # 过户费：万分之0.1（双向收取，与实盘一致）
    TRANSFER_FEE_RATE = 0.00001

    # 最低手续费5元
    MIN_COMMISSION = 5.0

    # 涨跌幅限制：10%
    PRICE_LIMIT = 0.1

    # T+1规则：True表示启用
    T1_RULE = True

    # ========== 策略配置 ==========
    # 策略类型（共36种量化策略，统一管理不再区分基础和优化）
    STRATEGY_TYPE = "rsi"

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
    TAKE_PROFIT_RATIO = 0.2

    # 样本外测试比例：预留最后多少比例的数据作为样本外测试，不参与参数优化
    OUT_OF_SAMPLE_RATIO = 0.2

    # ========== 日志配置 ==========
    # 日志级别：DEBUG, INFO, WARNING, ERROR
    LOG_LEVEL = "INFO"

    # 日志文件保留天数
    LOG_RETENTION_DAYS = 7

    # ========== 热点板块策略配置 ==========
    # 热点板块缓存有效期：24小时
    HOT_PLATE_CACHE_EXPIRE = 24 * 3600
    # 板块成分股缓存有效期：7天
    PLATE_STOCK_CACHE_EXPIRE = 7 * 24 * 3600
    # 热度分数权重：涨跌幅权重
    HOT_SCORE_CHANGE_WEIGHT = 0.4
    # 热度分数权重：上涨家数占比权重
    HOT_SCORE_RISE_RATIO_WEIGHT = 0.3
    # 热度分数权重：换手率权重
    HOT_SCORE_TURNOVER_WEIGHT = 0.3
    # 默认热点周期：最近3天
    HOT_PERIOD_DEFAULT = 3
    # 默认取TOP N个热点板块
    HOT_TOP_N_DEFAULT = 10

    # ========== 模拟盘配置 ==========
    # 模拟盘数据存储目录
    PAPER_TRADE_DATA_DIR = PROJECT_ROOT / "paper_trade_data"
    # 模拟盘默认初始资金
    PAPER_TRADE_INITIAL_CAPITAL = 1000000.0  # 可自定义，默认100万
    # 单只股票最大仓位比例
    PAPER_TRADE_MAX_POSITION_RATIO = 0.15  # 可自定义，默认15%
    # 加权投票阈值：达到总权重的多少比例执行交易
    PAPER_TRADE_SIGNAL_THRESHOLD = 0.6  # 默认60%
    # 自选股票池文件路径
    STOCK_POOL_FILE = CONFIG_DIR / "stock_pool.txt"

    # ========== 邮件通知配置 ==========
    EMAIL_NOTIFICATION_ENABLED = False
    EMAIL_SMTP_SERVER = "smtp.qq.com"
    EMAIL_SMTP_PORT = 465
    EMAIL_SENDER = ""
    EMAIL_SENDER_PASSWORD = os.getenv("QUANT_EMAIL_PASSWORD", "")  # 从环境变量读取授权码，默认空
    EMAIL_RECIPIENTS = []  # 收件人列表

    @classmethod
    def ensure_dirs(cls):
        """确保所有目录存在"""
        from utils.common_utils import CommonUtils
        dirs = [
            cls.LOG_DIR,
            cls.SAVED_DATA_DIR,
            cls.REPORTS_DIR,
            cls.TEMP_DIR,
            cls.CONFIG_DIR,
            cls.PAPER_TRADE_DATA_DIR,
            cls.PAPER_TRADE_DATA_DIR / "reports",
        ]
        for dir_path in dirs:
            CommonUtils.ensure_dir_exists(dir_path)

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
    def calculate_fees(cls, amount, is_sell=False, stock_code=None):
        """
        计算交易费用

        参数:
            amount: 交易金额
            is_sell: 是否为卖出
            stock_code: 股票代码，用于判断是否收取过户费（沪市股票收取，深市免收）

        返回:
            总手续费
        """
        # 手续费
        commission = max(amount * cls.COMMISSION_RATE, cls.MIN_COMMISSION)

        # 过户费（双向，仅沪市股票收取）
        transfer_fee = 0.0
        if stock_code and stock_code.startswith(cls.STOCK_PREFIX_SH):
            transfer_fee = amount * cls.TRANSFER_FEE_RATE

        # 印花税（仅卖出）
        stamp_duty = amount * cls.STAMP_DUTY_RATE if is_sell else 0.0

        return commission + transfer_fee + stamp_duty

    @classmethod
    def load_stock_pool(cls) -> list:
        """加载自选股票池"""
        stock_codes = []
        if not cls.STOCK_POOL_FILE.exists():
            # 如果股票池文件不存在，返回默认的上证50前10只
            return cls.STOCK_CODES[:10]

        try:
            with open(cls.STOCK_POOL_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    # 提取股票代码，忽略后面的注释
                    code = line.split('#')[0].strip()
                    if code:
                        stock_codes.append(code)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"加载股票池文件失败：{str(e)}，使用默认股票池")
            return cls.STOCK_CODES[:10]

        return stock_codes if stock_codes else cls.STOCK_CODES[:10]
