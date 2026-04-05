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
            return self._load_data(stock_code, period)

        df = None
        last_error = None

        # 首选数据源：akshare
        if AK_AVAILABLE:
            try:
                self.logger.info(f"尝试使用 akshare 数据源: {stock_code}")
                df = self._fetch_from_akshare(stock_code, start_date, end_date, period)
                if df is not None and not df.empty:
                    self.logger.info(f"akshare 数据源获取成功: {stock_code}")
                else:
                    df = None
                    self.logger.warning(f"akshare 返回空数据，尝试备用数据源")
            except Exception as e:
                last_error = e
                self.logger.warning(f"akshare 数据源失败: {str(e)}，尝试备用数据源")
                df = None

        # 备用数据源：baostock（仅支持日线）
        if df is None and BAOSTOCK_AVAILABLE and period == 'daily':
            try:
                self.logger.info(f"尝试使用 baostock 数据源: {stock_code}")
                df = self._fetch_from_baostock(stock_code, start_date, end_date)
                if df is not None and not df.empty:
                    self.logger.info(f"baostock 数据源获取成功: {stock_code}")
                else:
                    df = None
                    self.logger.warning(f"baostock 返回空数据")
            except Exception as e:
                last_error = e
                self.logger.warning(f"baostock 数据源失败: {str(e)}")
                df = None

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

            # 获取新数据（使用多数据源支持）
            new_df = None
            last_error = None

            # 首选数据源：akshare
            if AK_AVAILABLE:
                try:
                    self.logger.info(f"尝试使用 akshare 更新: {stock_code}")
                    new_df = self._fetch_from_akshare(stock_code, update_start, update_end, period)
                    if new_df is not None and not new_df.empty:
                        self.logger.info(f"akshare 更新成功: {stock_code}")
                    else:
                        new_df = None
                        self.logger.warning(f"akshare 返回空数据，尝试备用数据源")
                except Exception as e:
                    last_error = e
                    self.logger.warning(f"akshare 更新失败: {str(e)}，尝试备用数据源")
                    new_df = None

            # 备用数据源：baostock（仅支持日线）
            if new_df is None and BAOSTOCK_AVAILABLE and period == 'daily':
                try:
                    self.logger.info(f"尝试使用 baostock 更新: {stock_code}")
                    new_df = self._fetch_from_baostock(stock_code, update_start, update_end)
                    if new_df is not None and not new_df.empty:
                        self.logger.info(f"baostock 更新成功: {stock_code}")
                    else:
                        new_df = None
                        self.logger.warning(f"baostock 返回空数据")
                except Exception as e:
                    last_error = e
                    self.logger.warning(f"baostock 更新失败: {str(e)}")
                    new_df = None

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

    def fetch_all_stocks(self):
        """
        下载所有配置的股票数据

        返回:
            dict: {股票代码: DataFrame}
        """
        results = {}
        stock_codes = self.config.get_stock_list()

        for stock_code in stock_codes:
            self.logger.info(f"处理股票: {stock_code}")
            df = self.fetch_stock_data(
                stock_code,
                self.config.get_start_date(),
                self.config.get_end_date(),
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

        self.logger.info(f"数据下载完成，成功获取 {len(results)}/{len(stock_codes)} 只股票")
        return results

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
        """从 akshare 获取数据"""
        code = stock_code.lower()

        if period == 'daily':
            self.logger.info(f"调用 akshare 获取日线数据: {code}")
            df = ak.stock_zh_a_hist(
                symbol=code.replace('sh', '').replace('sz', ''),
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            column_mapping = {
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume',
                '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_chg',
                '涨跌额': 'change', '换手率': 'turnover'
            }
            df = df.rename(columns=column_mapping)

        elif period == '60min':
            self.logger.info(f"调用 akshare 获取60分钟线数据: {code}")
            try:
                df = ak.stock_zh_a_hist_min_em(
                    symbol=code.replace('sh', '').replace('sz', ''),
                    period="60",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                column_mapping = {
                    '时间': 'date', '开盘': 'open', '收盘': 'close',
                    '最高': 'high', '最低': 'low', '成交量': 'volume',
                    '成交额': 'amount'
                }
                df = df.rename(columns=column_mapping)
            except Exception as e:
                self.logger.warning(f"60分钟线数据失败，使用日线替代: {str(e)}")
                df = ak.stock_zh_a_hist(
                    symbol=code.replace('sh', '').replace('sz', ''),
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                column_mapping = {
                    '日期': 'date', '开盘': 'open', '收盘': 'close',
                    '最高': 'high', '最低': 'low', '成交量': 'volume',
                    '成交额': 'amount', '振幅': 'amplitude', '涨跌幅': 'pct_chg',
                    '涨跌额': 'change', '换手率': 'turnover'
                }
                df = df.rename(columns=column_mapping)
        else:
            raise ValueError(f"不支持的周期: {period}")

        time.sleep(0.5)
        return df

    def _fetch_from_baostock(self, stock_code, start_date, end_date):
        """从 baostock 获取数据（仅支持日线）"""
        if stock_code.startswith('sh'):
            bs_code = f"sh.{stock_code[2:]}"
        elif stock_code.startswith('sz'):
            bs_code = f"sz.{stock_code[2:]}"
        else:
            bs_code = stock_code
        
        if len(start_date) == 8:
            start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
        if len(end_date) == 8:
            end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
        
        lg = bs.login()
        if lg.error_code != '0':
            self.logger.error(f"baostock登录失败: {lg.error_msg}")
            raise RuntimeError(f"baostock登录失败: {lg.error_msg}")
        
        try:
            self.logger.info(f"调用 baostock 查询数据: {bs_code}, {start_date} 到 {end_date}")
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
            
            self.logger.info(f"baostock获取成功: {len(df)} 条记录")
            return df
        
        finally:
            bs.logout()

    def _load_data(self, stock_code, period='daily'):
        """从本地加载数据"""
        save_path = self.save_dir / f"{stock_code}_{period}.csv"
        if save_path.exists():
            df = pd.read_csv(save_path)
            self.logger.info(f"从本地加载数据: {save_path}")
            return df
        else:
            self.logger.warning(f"本地数据不存在: {save_path}")
            return None

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
