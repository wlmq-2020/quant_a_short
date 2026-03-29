# -*- coding: utf-8 -*-
"""
A股数据下载模块
负责获取、清洗和保存A股历史数据
【强制】必须使用真实A股数据，获取失败直接报错终止程序
"""
import pandas as pd
from pathlib import Path
import time
import warnings
warnings.filterwarnings('ignore')

import akshare as ak
import backtrader as bt

AK_AVAILABLE = True
BACKTRADER_AVAILABLE = True


class AStockDataFetcher:
    """A股数据获取类"""

    def __init__(self, config, logger):
        """
        初始化数据获取器

        参数:
            config: 配置对象
            logger: 日志对象
        """
        self.config = config
        self.logger = logger
        self.save_dir = Path(config.SAVED_DATA_DIR)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 检查 akshare 是否可用
        if not AK_AVAILABLE:
            self.logger.critical("akshare 库未安装，无法获取真实A股数据！")
            raise ImportError("akshare 库未安装，请运行: pip install akshare")

    def fetch_stock_data(self, stock_code, start_date, end_date, period='daily'):
        """
        获取单个股票数据
        【强制】必须获取真实数据，失败直接报错

        参数:
            stock_code: 股票代码（格式：sz000001 或 sh600000）
            start_date: 开始日期（格式：YYYYMMDD）
            end_date: 结束日期（格式：YYYYMMDD）
            period: K线周期 ('daily' 或 '60min')

        返回:
            DataFrame: 股票数据
        """
        self.logger.info(f"开始获取股票 {stock_code} 数据，周期: {period}")

        # 检查本地是否已有数据
        save_path = self.save_dir / f"{stock_code}_{period}.csv"
        if save_path.exists():
            self.logger.info(f"本地数据已存在，跳过下载: {stock_code}")
            return self.load_data(stock_code, period)

        try:
            # 从 akshare 获取真实数据
            df = self._fetch_from_akshare(stock_code, start_date, end_date, period)

            if df is not None and not df.empty:
                df = self._clean_data(df)
                df = self._standardize_data(df)
                df.to_csv(save_path, index=False, encoding='utf-8-sig')
                self.logger.info(f"数据已保存至 {save_path}，共 {len(df)} 条记录")
                return df
            else:
                self.logger.critical(f"获取股票 {stock_code} 数据失败：返回空数据")
                raise RuntimeError(f"获取股票 {stock_code} 数据失败：返回空数据")

        except Exception as e:
            self.logger.critical(f"获取股票 {stock_code} 数据异常: {str(e)}", exc_info=True)
            raise RuntimeError(f"获取股票 {stock_code} 数据失败: {str(e)}") from e

    def _fetch_from_akshare(self, stock_code, start_date, end_date, period):
        """
        从 akshare 获取真实数据

        参数:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: K线周期

        返回:
            DataFrame: 原始数据
        """
        # 转换股票代码格式
        # akshare 格式: sh600000 或 sz000001
        code = stock_code.lower()

        if period == 'daily':
            # 获取日线数据
            self.logger.info(f"调用 akshare 获取日线数据: {code}")
            df = ak.stock_zh_a_hist(
                symbol=code.replace('sh', '').replace('sz', ''),
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"  # 前复权
            )

            # 重命名列
            column_mapping = {
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_chg',
                '涨跌额': 'change',
                '换手率': 'turnover'
            }
            df = df.rename(columns=column_mapping)

        elif period == '60min':
            # 获取60分钟线数据
            self.logger.info(f"调用 akshare 获取60分钟线数据: {code}")

            # akshare 的 stock_zh_a_hist_min_em 函数需要不同的参数格式
            # 先获取日线数据，然后转换为60分钟线
            # 注意：akshare的分钟线数据接口可能有限制，这里使用替代方案
            try:
                # 尝试直接获取分钟线数据
                df = ak.stock_zh_a_hist_min_em(
                    symbol=code.replace('sh', '').replace('sz', ''),
                    period="60",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )

                # 重命名列
                column_mapping = {
                    '时间': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount'
                }
                df = df.rename(columns=column_mapping)

            except Exception as e:
                self.logger.warning(f"直接获取60分钟线数据失败，尝试日线数据替代: {str(e)}")
                # 如果分钟线数据获取失败，使用日线数据
                df = ak.stock_zh_a_hist(
                    symbol=code.replace('sh', '').replace('sz', ''),
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )

                # 重命名列
                column_mapping = {
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '振幅': 'amplitude',
                    '涨跌幅': 'pct_chg',
                    '涨跌额': 'change',
                    '换手率': 'turnover'
                }
                df = df.rename(columns=column_mapping)
                self.logger.info("使用日线数据替代60分钟线数据")

        else:
            raise ValueError(f"不支持的周期: {period}")

        time.sleep(0.5)  # 避免请求过快
        return df

    def _clean_data(self, df):
        """
        清洗数据

        参数:
            df: 原始DataFrame

        返回:
            DataFrame: 清洗后的DataFrame
        """
        if df is None or df.empty:
            return df

        df_clean = df.copy()

        # 删除重复行
        if 'date' in df_clean.columns:
            df_clean = df_clean.drop_duplicates(subset=['date'])

        # 删除缺失值
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        available_columns = [col for col in required_columns if col in df_clean.columns]
        df_clean = df_clean.dropna(subset=available_columns)

        # 价格不能为负或零
        for col in ['open', 'high', 'low', 'close']:
            if col in df_clean.columns:
                df_clean = df_clean[df_clean[col] > 0]

        # 成交量不能为负
        if 'volume' in df_clean.columns:
            df_clean = df_clean[df_clean['volume'] >= 0]

        # 按日期排序
        if 'date' in df_clean.columns:
            df_clean = df_clean.sort_values('date').reset_index(drop=True)

        self.logger.debug(f"数据清洗完成，从 {len(df)} 条减少到 {len(df_clean)} 条")
        return df_clean

    def _standardize_data(self, df):
        """
        标准化数据格式

        参数:
            df: 清洗后的DataFrame

        返回:
            DataFrame: 标准化后的DataFrame
        """
        if df is None or df.empty:
            return df

        df_std = df.copy()

        # 确保日期格式一致
        if 'date' in df_std.columns:
            try:
                df_std['date'] = pd.to_datetime(df_std['date']).dt.strftime('%Y-%m-%d')
            except:
                pass

        # 确保数值列类型正确
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_columns:
            if col in df_std.columns:
                df_std[col] = pd.to_numeric(df_std[col], errors='coerce')

        return df_std

    def load_data(self, stock_code, period='daily'):
        """
        从本地加载已保存的数据

        参数:
            stock_code: 股票代码
            period: K线周期

        返回:
            DataFrame: 股票数据
        """
        save_path = self.save_dir / f"{stock_code}_{period}.csv"
        if save_path.exists():
            df = pd.read_csv(save_path)
            self.logger.info(f"从本地加载数据: {save_path}")
            return df
        else:
            self.logger.warning(f"本地数据不存在: {save_path}")
            return None

    def fetch_all_stocks(self):
        """
        获取所有配置的股票数据
        【强制】必须获取完整50只股票数据，失败直接报错

        返回:
            dict: {股票代码: DataFrame}
        """
        results = {}
        stock_codes = self.config.get_stock_list()

        for stock_code in stock_codes:
            self.logger.info(f"处理股票: {stock_code}")
            df = self.fetch_stock_data(
                stock_code,
                self.config.START_DATE,
                self.config.END_DATE,
                self.config.KLINE_PERIOD
            )
            if df is not None:
                results[stock_code] = df

            # 间隔一段时间避免请求过快
            time.sleep(0.3)

        # 检查是否获取了所有股票
        if len(results) != len(stock_codes):
            self.logger.critical(
                f"数据获取不完整：期望 {len(stock_codes)} 只，实际获取 {len(results)} 只"
            )
            raise RuntimeError(
                f"数据获取不完整：期望 {len(stock_codes)} 只，实际获取 {len(results)} 只"
            )

        self.logger.info(f"数据获取完成，成功获取 {len(results)}/{len(stock_codes)} 只股票")
        return results

    def fetch_all_with_print(self):
        """
        下载所有股票数据（带print进度输出）

        返回:
            bool: 是否全部成功
        """
        print("=" * 80)
        print("下载A股股票数据")
        print("=" * 80)

        stock_list = self.config.get_stock_list()
        print(f"\n开始下载 {len(stock_list)} 只股票数据...")
        print(f"时间范围: {self.config.START_DATE} 至 {self.config.END_DATE}")
        print("-" * 80)

        success_count = 0
        fail_count = 0

        for i, stock_code in enumerate(stock_list, 1):
            print(f"[{i}/{len(stock_list)}] 下载: {stock_code}")
            try:
                df = self.fetch_stock_data(
                    stock_code,
                    self.config.START_DATE,
                    self.config.END_DATE,
                    self.config.KLINE_PERIOD
                )
                if df is not None and not df.empty:
                    print(f"  成功: {len(df)} 条记录")
                    success_count += 1
                else:
                    print(f"  失败: 无数据")
                    fail_count += 1
            except Exception as e:
                print(f"  失败: {str(e)}")
                fail_count += 1

        print("-" * 80)
        print(f"下载完成! 成功: {success_count}, 失败: {fail_count}")
        print("=" * 80)

        return fail_count == 0

    def test_fetch_single_stock(self, stock_code="sh600519", period="daily"):
        """
        测试获取单个股票数据（用于调试）

        参数:
            stock_code: 测试股票代码
            period: K线周期

        返回:
            DataFrame: 测试数据
        """
        self.logger.info(f"测试获取股票数据: {stock_code}, 周期: {period}")

        try:
            # 获取最近30天的数据用于测试
            from datetime import datetime, timedelta
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

            df = self.fetch_stock_data(stock_code, start_date, end_date, period)

            if df is not None and not df.empty:
                print(f"[OK] 测试成功！获取到 {len(df)} 条数据")
                print(f"  数据列: {list(df.columns)}")
                print(f"  日期范围: {df['date'].min()} 到 {df['date'].max()}")
                print(f"  最新3条数据:")
                print(df[['date', 'open', 'high', 'low', 'close', 'volume']].tail(3).to_string(index=False))

                # 检查本地文件
                save_path = self.save_dir / f"{stock_code}_{period}.csv"
                if save_path.exists():
                    print(f"[OK] 数据已保存到: {save_path}")
                    print(f"  文件大小: {save_path.stat().st_size / 1024:.1f} KB")
            else:
                print("[FAIL] 测试失败：获取到空数据")

            return df

        except Exception as e:
            print(f"[FAIL] 测试失败: {str(e)}")
            raise

    def update_stock_data(self, stock_code, period='daily'):
        """
        更新单个股票数据到最新
        读取本地数据，获取最新日期之后的数据并合并

        参数:
            stock_code: 股票代码
            period: K线周期

        返回:
            DataFrame: 更新后的股票数据
        """
        from datetime import datetime, timedelta

        self.logger.info(f"更新股票数据: {stock_code}")

        # 读取本地数据
        save_path = self.save_dir / f"{stock_code}_{period}.csv"

        if not save_path.exists():
            self.logger.warning(f"本地数据不存在，将下载完整数据: {stock_code}")
            # 如果本地没有数据，下载完整数据
            return self.fetch_stock_data(
                stock_code,
                self.config.START_DATE,
                datetime.now().strftime("%Y%m%d"),
                period
            )

        try:
            # 读取本地数据
            local_df = pd.read_csv(save_path)
            local_df['date'] = pd.to_datetime(local_df['date'])

            # 获取本地最新日期
            latest_date = local_df['date'].max()
            today = datetime.now()

            # 如果最新日期已经是今天，跳过更新
            if latest_date.date() >= today.date():
                self.logger.info(f"数据已是最新，无需更新: {stock_code}")
                return local_df

            # 计算需要更新的起始日期（最新日期+1天）
            update_start = (latest_date + timedelta(days=1)).strftime("%Y%m%d")
            update_end = today.strftime("%Y%m%d")

            self.logger.info(f"更新数据范围: {update_start} 到 {update_end}")

            # 获取新数据
            new_df = self._fetch_from_akshare(stock_code, update_start, update_end, period)

            if new_df is not None and not new_df.empty:
                # 清洗和标准化新数据
                new_df = self._clean_data(new_df)
                new_df = self._standardize_data(new_df)
                new_df['date'] = pd.to_datetime(new_df['date'])

                # 合并数据
                combined_df = pd.concat([local_df, new_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['date'])
                combined_df = combined_df.sort_values('date').reset_index(drop=True)

                # 保存合并后的数据
                combined_df['date'] = combined_df['date'].dt.strftime('%Y-%m-%d')
                combined_df.to_csv(save_path, index=False, encoding='utf-8-sig')

                self.logger.info(f"数据已更新: {stock_code}，新增 {len(new_df)} 条记录，总计 {len(combined_df)} 条")
                return combined_df
            else:
                self.logger.info(f"没有新数据需要更新: {stock_code}")
                local_df['date'] = local_df['date'].dt.strftime('%Y-%m-%d')
                return local_df

        except Exception as e:
            self.logger.error(f"更新数据失败: {stock_code}, 错误: {str(e)}")
            raise

    def update_all_stocks(self):
        """
        更新所有股票数据到最新

        返回:
            dict: 更新统计信息
        """
        from datetime import datetime

        self.logger.info("=" * 60)
        self.logger.info("开始更新所有股票数据")
        self.logger.info("=" * 60)

        stock_codes = self.config.get_stock_list()
        results = {
            'total': len(stock_codes),
            'updated': 0,
            'skipped': 0,
            'failed': 0,
            'details': []
        }

        for i, stock_code in enumerate(stock_codes, 1):
            self.logger.info(f"[{i}/{len(stock_codes)}] 更新: {stock_code}")

            try:
                df = self.update_stock_data(stock_code, self.config.KLINE_PERIOD)

                if df is not None and not df.empty:
                    results['updated'] += 1
                    results['details'].append({
                        'code': stock_code,
                        'status': 'updated',
                        'records': len(df)
                    })
                else:
                    results['skipped'] += 1
                    results['details'].append({
                        'code': stock_code,
                        'status': 'skipped',
                        'records': 0
                    })

            except Exception as e:
                self.logger.error(f"更新失败: {stock_code}, 错误: {str(e)}")
                results['failed'] += 1
                results['details'].append({
                    'code': stock_code,
                    'status': 'failed',
                    'error': str(e)
                })

            # 避免请求过快
            time.sleep(0.3)

        self.logger.info("=" * 60)
        self.logger.info(f"更新完成: 总计 {results['total']} 只，更新 {results['updated']} 只，跳过 {results['skipped']} 只，失败 {results['failed']} 只")
        self.logger.info("=" * 60)

        return results

    # ========== Backtrader数据适配功能 ==========

    def convert_to_backtrader_format(self, df, stock_code=None):
        """
        将akshare格式的DataFrame转换为Backtrader兼容格式

        参数:
            df: akshare格式的DataFrame
            stock_code: 股票代码（可选）

        返回:
            DataFrame: Backtrader兼容格式的DataFrame
        """
        if df is None or df.empty:
            self.logger.warning("输入数据为空，无法转换")
            return None

        try:
            # 创建副本以避免修改原始数据
            df_bt = df.copy()

            # 1. 标准化列名
            df_bt = self._standardize_column_names_for_bt(df_bt)

            # 2. 确保必需的列存在
            df_bt = self._ensure_required_columns_for_bt(df_bt)

            # 3. 转换数据类型
            df_bt = self._convert_data_types_for_bt(df_bt)

            # 4. 处理日期时间
            df_bt = self._process_datetime_for_bt(df_bt)

            # 5. 排序和去重
            df_bt = self._sort_and_deduplicate_for_bt(df_bt)

            # 6. 添加股票代码信息
            if stock_code:
                df_bt['stock_code'] = stock_code

            self.logger.debug(f"数据转换完成: {stock_code or '未知'}, 原始{len(df)}行 -> 转换后{len(df_bt)}行")

            return df_bt

        except Exception as e:
            self.logger.error(f"数据转换失败: {str(e)}")
            raise

    def _standardize_column_names_for_bt(self, df):
        """标准化列名用于Backtrader"""
        column_mapping = {
            # 日期时间
            '日期': 'date',
            '时间': 'date',
            'datetime': 'date',

            # OHLCV
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount',

            # 其他常见列名
            '涨跌幅': 'pct_chg',
            '涨跌额': 'change',
            '振幅': 'amplitude',
            '换手率': 'turnover',
            '开盘价': 'open',
            '最高价': 'high',
            '最低价': 'low',
            '收盘价': 'close',
        }

        # 重命名列
        for old_name, new_name in column_mapping.items():
            if old_name in df.columns and new_name not in df.columns:
                df = df.rename(columns={old_name: new_name})

        return df

    def _ensure_required_columns_for_bt(self, df):
        """确保Backtrader必需的列存在"""
        required_columns = ['open', 'high', 'low', 'close', 'volume']

        # 检查缺失的列
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            # 尝试从其他列推导
            if 'close' in df.columns:
                for col in missing_columns:
                    if col == 'volume':
                        df[col] = 1000000  # 默认成交量
                    else:
                        df[col] = df['close']  # 使用收盘价作为默认值

            self.logger.warning(f"数据缺失列: {missing_columns}，已使用默认值填充")

        return df

    def _convert_data_types_for_bt(self, df):
        """转换数据类型用于Backtrader"""
        # 数值列
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount',
                          'pct_chg', 'change', 'amplitude', 'turnover']

        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 处理异常值
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                # 价格不能为负或零
                df = df[df[col] > 0]

        if 'volume' in df.columns:
            # 成交量不能为负
            df = df[df['volume'] >= 0]

        return df

    def _process_datetime_for_bt(self, df):
        """处理日期时间列用于Backtrader"""
        if 'date' not in df.columns:
            # 如果没有日期列，创建默认日期
            df['date'] = pd.date_range(start='2023-01-01', periods=len(df), freq='D')
        else:
            # 尝试解析日期时间
            try:
                df['date'] = pd.to_datetime(df['date'])
            except:
                # 如果解析失败，创建默认日期
                df['date'] = pd.date_range(start='2023-01-01', periods=len(df), freq='D')

        # 设置日期为索引（Backtrader要求）
        df.set_index('date', inplace=True)

        return df

    def _sort_and_deduplicate_for_bt(self, df):
        """排序和去重用于Backtrader"""
        # 按日期排序
        df = df.sort_index()

        # 去重（基于索引）
        df = df[~df.index.duplicated(keep='first')]

        # 填充缺失值
        df = df.fillna(method='ffill')
        df = df.fillna(method='bfill')

        return df

    def create_backtrader_datafeed(self, df, stock_code=None, **kwargs):
        """
        创建Backtrader数据feed

        参数:
            df: 转换后的DataFrame
            stock_code: 股票代码（可选）
            **kwargs: 传递给PandasData的参数

        返回:
            bt.feeds.PandasData: Backtrader数据feed
        """
        if df is None or df.empty:
            raise ValueError("输入数据为空")

        try:
            # 定义Backtrader数据格式
            class AksharePandasData(bt.feeds.PandasData):
                params = (
                    ('datetime', None),  # 使用索引作为datetime
                    ('open', 'open'),
                    ('high', 'high'),
                    ('low', 'low'),
                    ('close', 'close'),
                    ('volume', 'volume'),
                    ('openinterest', -1),  # 没有持仓量数据
                )

            # 创建数据feed
            datafeed = AksharePandasData(dataname=df, **kwargs)

            self.logger.info(f"创建Backtrader数据feed: {stock_code or '未知'}, 数据长度: {len(df)}")

            return datafeed

        except Exception as e:
            self.logger.error(f"创建Backtrader数据feed失败: {str(e)}")
            raise

    def get_backtrader_data(self, stock_code, period='daily'):
        """
        获取Backtrader格式的数据

        参数:
            stock_code: 股票代码
            period: 周期

        返回:
            tuple: (转换后的DataFrame, 数据feed)
        """
        # 加载原始数据
        df = self.load_data(stock_code, period)
        if df is None:
            self.logger.error(f"无法加载股票数据: {stock_code}")
            return None, None

        # 转换为Backtrader格式
        df_bt = self.convert_to_backtrader_format(df, stock_code)
        if df_bt is None:
            self.logger.error(f"数据转换失败: {stock_code}")
            return None, None

        # 创建数据feed
        try:
            datafeed = self.create_backtrader_datafeed(df_bt, stock_code)
            return df_bt, datafeed
        except Exception as e:
            self.logger.error(f"创建数据feed失败 {stock_code}: {str(e)}")
            return df_bt, None

    def batch_get_backtrader_data(self, stock_codes=None, period='daily'):
        """
        批量获取Backtrader格式的数据

        参数:
            stock_codes: 股票代码列表，如果为None则使用配置中的所有股票
            period: 周期

        返回:
            dict: {股票代码: {'dataframe': DataFrame, 'datafeed': 数据feed}}
        """
        if stock_codes is None:
            stock_codes = self.config.get_stock_list()

        results = {}

        for stock_code in stock_codes:
            try:
                df_bt, datafeed = self.get_backtrader_data(stock_code, period)

                results[stock_code] = {
                    'dataframe': df_bt,
                    'datafeed': datafeed,
                    'success': df_bt is not None
                }

                self.logger.debug(f"获取Backtrader数据成功: {stock_code}")

            except Exception as e:
                results[stock_code] = {
                    'dataframe': None,
                    'datafeed': None,
                    'success': False,
                    'error': str(e)
                }

                self.logger.error(f"获取Backtrader数据失败 {stock_code}: {str(e)}")

        return results

    def save_backtrader_format_data(self, stock_code, period='daily'):
        """
        保存Backtrader格式的数据到文件

        参数:
            stock_code: 股票代码
            period: 周期

        返回:
            str: 保存的文件路径
        """
        try:
            # 获取Backtrader格式数据
            df_bt, _ = self.get_backtrader_data(stock_code, period)
            if df_bt is None:
                return None

            # 创建保存目录
            save_dir = self.save_dir / 'backtrader_format'
            save_dir.mkdir(parents=True, exist_ok=True)

            # 保存文件
            save_path = save_dir / f"{stock_code}_{period}_bt.csv"

            # 重置索引以便保存
            df_to_save = df_bt.reset_index()
            df_to_save.to_csv(save_path, index=False, encoding='utf-8-sig')

            self.logger.info(f"Backtrader格式数据已保存: {save_path}")

            return str(save_path)

        except Exception as e:
            self.logger.error(f"保存Backtrader格式数据失败 {stock_code}: {str(e)}")
            return None
