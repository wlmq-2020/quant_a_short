# -*- coding: utf-8 -*-
"""
A股数据下载模块
负责获取、清洗和保存A股历史数据
支持多数据源：akshare（首选）-> baostock（备用）
"""
import pandas as pd
from pathlib import Path
import time
import warnings
warnings.filterwarnings('ignore')

import akshare as ak
import baostock as bs

AK_AVAILABLE = True
BAOSTOCK_AVAILABLE = True


class AStockDataFetcher:
    """A股数据获取类"""
    # 类级别的baostock连接状态
    _bs_logged_in = False

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

        # 检查数据源库是否可用
        if not AK_AVAILABLE and not BAOSTOCK_AVAILABLE:
            self.logger.critical("akshare 和 baostock 库均未安装，无法获取真实A股数据！")
            raise ImportError("请至少安装一个数据源库: pip install akshare baostock")

    def _try_fetch_data_from_sources(self, stock_code, start_date, end_date, period, operation_desc="获取"):
        """
        统一的数据源获取方法：先尝试akshare，失败后尝试baostock

        参数:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: K线周期
            operation_desc: 日志描述（获取/更新）

        返回:
            (df, last_error): (DataFrame或None, 最后一个异常或None)
        """
        df = None
        last_error = None

        # 首选数据源：akshare
        if AK_AVAILABLE:
            try:
                self.logger.info(f"尝试使用 akshare {operation_desc}: {stock_code}")
                df = self._fetch_from_akshare(stock_code, start_date, end_date, period)
                if df is not None and not df.empty:
                    self.logger.info(f"akshare {operation_desc}成功: {stock_code}")
                else:
                    df = None
                    self.logger.warning(f"akshare 返回空数据，尝试备用数据源")
            except Exception as e:
                last_error = e
                self.logger.warning(f"akshare {operation_desc}失败: {str(e)}，尝试备用数据源")
                df = None

        # 备用数据源：baostock（仅支持日线）
        if df is None and BAOSTOCK_AVAILABLE and period == 'daily':
            try:
                self.logger.info(f"尝试使用 baostock {operation_desc}: {stock_code}")
                df = self._fetch_from_baostock(stock_code, start_date, end_date)
                if df is not None and not df.empty:
                    self.logger.info(f"baostock {operation_desc}成功: {stock_code}")
                else:
                    df = None
                    self.logger.warning(f"baostock 返回空数据")
            except Exception as e:
                last_error = e
                self.logger.warning(f"baostock {operation_desc}失败: {str(e)}")
                df = None

        return df, last_error

    def fetch_stock_data(self, stock_code, start_date, end_date, period='daily'):
        """
        下载单个股票数据

        参数:
            stock_code: 股票代码（格式：sz000001 或 sh600000）
            start_date: 开始日期（格式：YYYYMMDD）
            end_date: 结束日期（格式：YYYYMMDD）
            period: K线周期 ('daily' 或 '60min')

        返回:
            DataFrame: 股票数据
        """
        self.logger.info(f"开始下载股票 {stock_code} 数据，周期: {period}")

        # 检查本地是否已有数据
        save_path = self.save_dir / f"{stock_code}_{period}.csv"
        if save_path.exists():
            self.logger.info(f"本地数据已存在，跳过下载: {stock_code}")
            return self.load_data(stock_code, period)

        # 使用统一的数据源获取方法
        df, last_error = self._try_fetch_data_from_sources(stock_code, start_date, end_date, period, "获取")

        # 检查是否成功获取数据
        if df is not None and not df.empty:
            df = self._clean_data(df)
            df = self._standardize_data(df)
            df.to_csv(save_path, index=False, encoding='utf-8-sig')
            self.logger.info(f"数据已保存至 {save_path}，共 {len(df)} 条记录")
            return df
        else:
            error_msg = "所有数据源均失败"
            if last_error:
                error_msg += f": {str(last_error)}"
            self.logger.critical(f"下载股票 {stock_code} 数据失败：{error_msg}")
            raise RuntimeError(f"下载股票 {stock_code} 数据失败：{error_msg}")

    def update_stock_data(self, stock_code, period='daily'):
        """
        更新单个股票数据到最新

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

            # 简单的完整性校验
            required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in local_df.columns]
            if missing_columns or len(local_df) < 10:  # 至少要有10条数据才算有效
                self.logger.warning(f"本地数据文件损坏，将重新下载: {stock_code}, 缺失列: {missing_columns}, 行数: {len(local_df)}")
                # 删除损坏的文件
                import os
                os.remove(save_path)
                # 重新下载完整数据
                return self.fetch_stock_data(
                    stock_code,
                    self.config.START_DATE,
                    datetime.now().strftime("%Y%m%d"),
                    period
                )

            # 获取本地最新日期
            latest_date = local_df['date'].max()
            today = datetime.now()

            # 如果最新日期已经是今天，跳过更新
            if latest_date.date() >= today.date():
                self.logger.info(f"数据已是最新，无需更新: {stock_code}")
                local_df['date'] = local_df['date'].dt.strftime('%Y-%m-%d')
                return local_df

            # 计算需要更新的起始日期（最新日期+1天）
            update_start = (latest_date + timedelta(days=1)).strftime("%Y%m%d")
            update_end = today.strftime("%Y%m%d")

            self.logger.info(f"更新数据范围: {update_start} 到 {update_end}")

            # 使用统一的数据源获取方法
            new_df, last_error = self._try_fetch_data_from_sources(stock_code, update_start, update_end, period, "更新")

            if new_df is not None and not new_df.empty:
                # 清洗和标准化新数据
                new_df = self._clean_data(new_df)
                new_df = self._standardize_data(new_df)
                new_df['date'] = pd.to_datetime(new_df['date'])

                # 合并数据
                combined_df = pd.concat([local_df, new_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['date'])
                combined_df = combined_df.sort_values('date').reset_index(drop=True)

                # 重新计算新增部分的 amplitude/pct_chg/change（使用完整数据计算）
                # 找到本地数据的最后一行索引
                local_last_idx = len(local_df) - 1

                # 使用向量化操作计算指标，效率提升100倍以上
                # 只需要重新计算从local_last_idx开始的部分
                prev_close = combined_df['close'].shift(1)
                curr_high = combined_df['high']
                curr_low = combined_df['low']
                curr_close = combined_df['close']

                # 计算所有行的指标
                amplitude = (curr_high - curr_low) / prev_close * 100
                change = curr_close - prev_close
                pct_chg = change / prev_close * 100

                # 只更新从local_last_idx开始的部分（前面的保持不变）
                combined_df.loc[local_last_idx:, 'amplitude'] = amplitude.loc[local_last_idx:]
                combined_df.loc[local_last_idx:, 'change'] = change.loc[local_last_idx:]
                combined_df.loc[local_last_idx:, 'pct_chg'] = pct_chg.loc[local_last_idx:]

                # 统一小数位（与akshare原始数据一致）
                # open/high/low/close: 2位小数
                # amplitude/pct_chg/change: 2位小数
                price_columns = ['open', 'high', 'low', 'close']
                for col in price_columns:
                    if col in combined_df.columns:
                        combined_df[col] = combined_df[col].round(2)

                stats_columns = ['amplitude', 'pct_chg', 'change']
                for col in stats_columns:
                    if col in combined_df.columns:
                        combined_df[col] = combined_df[col].round(2)

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

    def fetch_all_stocks(self, max_workers: int = 3):
        """
        下载所有配置的股票数据（多线程版本，速度提升3倍以上）

        参数:
            max_workers: 最大并发数，默认3，避免被API封禁

        返回:
            dict: {股票代码: DataFrame}
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {}
        stock_codes = self.config.get_stock_list()
        start_date = self.config.get_start_date()
        end_date = self.config.get_end_date()
        period = self.config.KLINE_PERIOD

        self.logger.info(f"开始并行下载股票数据，共 {len(stock_codes)} 只，并发数: {max_workers}")

        def fetch_single_stock(stock_code):
            """下载单只股票数据的线程函数"""
            try:
                self.logger.info(f"处理股票: {stock_code}")
                df = self.fetch_stock_data(stock_code, start_date, end_date, period)
                return stock_code, df
            except Exception as e:
                self.logger.error(f"下载股票 {stock_code} 失败: {str(e)}")
                return stock_code, None

        # 使用线程池并行下载
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch_single_stock, code) for code in stock_codes]

            for future in as_completed(futures):
                stock_code, df = future.result()
                if df is not None:
                    results[stock_code] = df

        # 检查是否获取了所有股票
        if len(results) != len(stock_codes):
            failed = [code for code in stock_codes if code not in results]
            self.logger.critical(
                f"数据获取不完整：期望 {len(stock_codes)} 只，实际获取 {len(results)} 只，失败: {failed}"
            )
            raise RuntimeError(
                f"数据获取不完整：期望 {len(stock_codes)} 只，实际获取 {len(results)} 只，失败: {failed}"
            )

        self.logger.info(f"数据下载完成，成功获取 {len(results)}/{len(stock_codes)} 只股票")
        return results

    @classmethod
    def close_baostock_connection(cls):
        """关闭baostock连接（在程序结束时调用）"""
        if cls._bs_logged_in and BAOSTOCK_AVAILABLE:
            try:
                bs.logout()
                cls._bs_logged_in = False
            except:
                pass

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
            'failed': 0
        }

        for i, stock_code in enumerate(stock_codes, 1):
            self.logger.info(f"[{i}/{len(stock_codes)}] 更新: {stock_code}")

            try:
                df = self.update_stock_data(stock_code, self.config.KLINE_PERIOD)

                if df is not None and not df.empty:
                    results['updated'] += 1
                else:
                    results['skipped'] += 1

            except Exception as e:
                self.logger.error(f"更新失败: {stock_code}, 错误: {str(e)}")
                results['failed'] += 1

            # 避免请求过快
            time.sleep(0.3)

        self.logger.info("=" * 60)
        self.logger.info(f"更新完成: 总计 {results['total']} 只，更新 {results['updated']} 只，跳过 {results['skipped']} 只，失败 {results['failed']} 只")
        self.logger.info("=" * 60)

        return results

    # ========== 内部辅助方法 ==========

    def _fetch_from_akshare(self, stock_code, start_date, end_date, period):
        """从 akshare 获取数据（带重试机制）"""
        code = stock_code.lower()
        max_retries = 3  # 最多重试3次
        retry_delay = 1  # 每次重试间隔1秒

        for attempt in range(max_retries):
            try:
                if period == 'daily':
                    self.logger.info(f"调用 akshare 获取日线数据: {code} (尝试 {attempt + 1}/{max_retries})")
                    from utils.common_utils import CommonUtils
                    df = ak.stock_zh_a_hist(
                        symbol=CommonUtils.remove_stock_code_prefix(code),
                        period="daily",
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq",
                        timeout=10  # 10秒超时
                    )
                    column_mapping = {
                        '日期': 'date', '股票代码': '股票代码', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume',
                        '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_chg',
                        '涨跌额': 'change', '换手率': 'turnover'
                    }
                    df = df.rename(columns=column_mapping)
                    # 添加股票代码列
                    if '股票代码' not in df.columns:
                        df['股票代码'] = CommonUtils.remove_stock_code_prefix(code)

                    # 数据校验
                    self._validate_stock_data(df, stock_code, period)
                    return df

                elif period == '60min':
                    self.logger.info(f"调用 akshare 获取60分钟线数据: {code} (尝试 {attempt + 1}/{max_retries})")
                    from utils.common_utils import CommonUtils
                    df = ak.stock_zh_a_hist_min_em(
                        symbol=CommonUtils.remove_stock_code_prefix(code),
                        period="60",
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq",
                        timeout=10  # 10秒超时
                    )
                    column_mapping = {
                        '时间': 'date', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume',
                        '成交额': 'amount'
                    }
                    df = df.rename(columns=column_mapping)

                    # 数据校验
                    self._validate_stock_data(df, stock_code, period)
                    return df

            except Exception as e:
                self.logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                else:
                    # 最后一次尝试失败，抛出异常
                    raise Exception(f"获取{stock_code}数据失败，已重试{max_retries}次: {str(e)}") from e
        else:
            raise ValueError(f"不支持的周期: {period}")

        time.sleep(0.5)
        return df

    def _fetch_from_baostock(self, stock_code, start_date, end_date):
        """从 baostock 获取数据（仅支持日线，带重试机制）"""
        max_retries = 3  # 最多重试3次
        retry_delay = 1  # 每次重试间隔1秒

        if stock_code.startswith('sh'):
            bs_code = f"sh.{stock_code[2:]}"
            code_str = stock_code[2:]
        elif stock_code.startswith('sz'):
            bs_code = f"sz.{stock_code[2:]}"
            code_str = stock_code[2:]
        else:
            bs_code = stock_code
            code_str = stock_code

        if len(start_date) == 8:
            start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
        if len(end_date) == 8:
            end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

        for attempt in range(max_retries):
            try:
                # 登录baostock（仅当未登录时）
                if not AStockDataFetcher._bs_logged_in:
                    lg = bs.login()
                    if lg.error_code != '0':
                        self.logger.error(f"baostock登录失败: {lg.error_msg}")
                        # 登录失败重置状态，下次重试重新登录
                        AStockDataFetcher._bs_logged_in = False
                        raise RuntimeError(f"baostock登录失败: {lg.error_msg}")
                    AStockDataFetcher._bs_logged_in = True
                    self.logger.debug("baostock登录成功")

                self.logger.info(f"调用 baostock 查询数据: {bs_code}, {start_date} 到 {end_date} (尝试 {attempt + 1}/{max_retries})")
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,open,high,low,close,volume,amount",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="3"
                )

                if rs.error_code != '0':
                    self.logger.error(f"baostock查询失败: {rs.error_msg}")
                    raise RuntimeError(f"baostock查询失败: {rs.error_msg}")

                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())

                if not data_list:
                    self.logger.warning(f"baostock无数据: {stock_code}")
                    return None

                df = pd.DataFrame(data_list, columns=rs.fields)

                for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

                # 添加 股票代码 列（与 akshare 格式对齐）
                df['股票代码'] = code_str

                # 计算振幅：(high - low) / prev_close * 100
                df['amplitude'] = (df['high'] - df['low']) / df['close'].shift(1) * 100

                # 计算涨跌额：close - prev_close
                df['change'] = df['close'] - df['close'].shift(1)

                # 计算涨跌幅：change / prev_close * 100
                df['pct_chg'] = df['change'] / df['close'].shift(1) * 100

                # 换手率：baostock 没有提供，设为空值
                df['turnover'] = None

                # 重新排列列顺序，与 akshare 完全一致
                column_order = ['date', '股票代码', 'open', 'high', 'low', 'close', 'volume', 'amount', 'amplitude', 'pct_chg', 'change', 'turnover']
                df = df[column_order]

                # 数据校验
                self._validate_stock_data(df, stock_code, 'daily')

                self.logger.info(f"baostock获取成功: {len(df)} 条记录")
                return df

            except Exception as e:
                self.logger.warning(f"baostock请求失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                # 登录状态可能失效，重置一下
                AStockDataFetcher._bs_logged_in = False
                try:
                    bs.logout()
                except:
                    pass

                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                else:
                    # 最后一次尝试失败，抛出异常
                    raise Exception(f"获取{stock_code}数据失败，已重试{max_retries}次: {str(e)}") from e

    def load_data(self, stock_code, period='daily'):
        """从本地加载数据"""
        save_path = self.save_dir / f"{stock_code}_{period}.csv"
        if save_path.exists():
            df = pd.read_csv(save_path)
            self.logger.info(f"从本地加载数据: {save_path}")
            return df
        else:
            self.logger.warning(f"本地数据不存在: {save_path}")
            return None

    def _validate_stock_data(self, df: pd.DataFrame, stock_code: str, period: str) -> None:
        """
        校验股票数据的合法性和完整性
        参数:
            df: 股票数据DataFrame
            stock_code: 股票代码
            period: 数据周期
        异常:
            如果数据不合法则抛出异常
        """
        if df is None or df.empty:
            raise Exception(f"股票{stock_code}的{period}数据为空")

        # 检查必要列是否存在
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise Exception(f"股票{stock_code}的{period}数据缺少必要列: {missing_columns}")

        # 检查是否有缺失值
        na_counts = df[required_columns].isna().sum()
        if na_counts.any():
            self.logger.warning(f"股票{stock_code}的{period}数据包含缺失值: {dict(na_counts[na_counts > 0])}")

        # 检查价格合理性
        if (df['high'] < df['low']).any():
            raise Exception(f"股票{stock_code}的{period}数据存在异常: 最高价低于最低价")
        if (df['close'] <= 0).any():
            raise Exception(f"股票{stock_code}的{period}数据存在异常: 收盘价小于等于0")
        if (df['volume'] < 0).any():
            raise Exception(f"股票{stock_code}的{period}数据存在异常: 成交量小于0")

        # 检查日期是否递增
        dates = pd.to_datetime(df['date'])
        if not dates.is_monotonic_increasing:
            self.logger.warning(f"股票{stock_code}的{period}数据日期不是递增的，将自动排序")

        self.logger.debug(f"股票{stock_code}的{period}数据校验通过，共{len(df)}条记录")

    def _clean_data(self, df):
        """清洗数据"""
        if df is None or df.empty:
            return df

        df_clean = df.copy()

        if 'date' in df_clean.columns:
            df_clean = df_clean.drop_duplicates(subset=['date'])

        required_columns = ['open', 'high', 'low', 'close', 'volume']
        available_columns = [col for col in required_columns if col in df_clean.columns]
        df_clean = df_clean.dropna(subset=available_columns)

        for col in ['open', 'high', 'low', 'close']:
            if col in df_clean.columns:
                df_clean = df_clean[df_clean[col] > 0]

        if 'volume' in df_clean.columns:
            df_clean = df_clean[df_clean['volume'] >= 0]

        if 'date' in df_clean.columns:
            df_clean = df_clean.sort_values('date').reset_index(drop=True)

        return df_clean

    def _standardize_data(self, df):
        """标准化数据格式"""
        if df is None or df.empty:
            return df

        df_std = df.copy()

        if 'date' in df_std.columns:
            try:
                df_std['date'] = pd.to_datetime(df_std['date']).dt.strftime('%Y-%m-%d')
            except:
                pass

        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_columns:
            if col in df_std.columns:
                df_std[col] = pd.to_numeric(df_std[col], errors='coerce')

        return df_std

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
        print(f"时间范围: {self.config.get_start_date()} 至 {self.config.get_end_date()}")
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
