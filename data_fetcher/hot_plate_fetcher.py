#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
热点板块数据获取模块
支持在线获取东方财富热点板块数据，本地缓存，多进程安全访问
"""

import os
import json
import time
import datetime
from typing import List, Dict, Optional
import akshare as ak

from utils.file_rw_lock import FileRWLock
from utils.atomic_writer import AtomicWriter
from config import Config
from logger import get_logger

class HotPlateFetcher:
    """热点板块数据获取器"""

    # 缓存文件路径
    CACHE_FILE = Config.SAVED_DATA_DIR / 'hot_plates_cache.json'
    # 热点缓存有效期：24小时
    CACHE_EXPIRE = Config.HOT_PLATE_CACHE_EXPIRE
    # 板块成分股缓存有效期：7天
    PLATE_CACHE_EXPIRE = Config.PLATE_STOCK_CACHE_EXPIRE

    def __init__(self, offline_mode: bool = False):
        """
        初始化
        :param offline_mode: 离线模式，仅从缓存读取数据
        """
        self.offline_mode = offline_mode
        self._cache: Optional[Dict] = None
        self._lock = FileRWLock(str(self.CACHE_FILE) + '.lock')
        self.logger = get_logger()

    def get_hot_stocks(self, days: int = 3, top_n: int = 10, end_date: Optional[str] = None) -> List[str]:
        """
        获取最近N天的热点板块对应的股票列表
        :param days: 最近多少天的热点
        :param top_n: 取TOP N个热点板块
        :param end_date: 截止日期，格式为YYYYMMDD，不传则为当前日期
        :return: 股票代码列表
        """
        hot_plates = self.get_hot_plates(days, top_n, end_date)
        all_stocks = set()

        for plate in hot_plates:
            stocks = self.get_plate_stocks(plate['plate_code'])
            all_stocks.update(stocks)

        return list(all_stocks)

    def get_hot_plates(self, days: int = 3, top_n: int = 10, end_date: Optional[str] = None) -> List[Dict]:
        """
        获取最近N天的热点板块列表
        :param days: 最近多少天的热点
        :param top_n: 取TOP N个热点板块
        :param end_date: 截止日期，格式为YYYYMMDD，不传则为当前日期
        :return: 热点板块列表，每个元素包含plate_code, plate_name, hot_score
        """
        cache = self._get_cache()

        # 按日期筛选最近N天的数据
        if end_date is None:
            end_date = datetime.datetime.now().strftime('%Y%m%d')
        end_dt = datetime.datetime.strptime(end_date, '%Y%m%d')
        start_date = (end_dt - datetime.timedelta(days=days)).strftime('%Y%m%d')

        hot_plates = []
        for date in cache.get('hot_plates', {}):
            if start_date <= date <= end_date:
                hot_plates.extend(cache['hot_plates'][date])

        # 按热度排序并去重
        plate_scores = {}
        for plate in hot_plates:
            code = plate['plate_code']
            if code not in plate_scores or plate['hot_score'] > plate_scores[code]['hot_score']:
                plate_scores[code] = plate

        # 取TOP N
        sorted_plates = sorted(plate_scores.values(), key=lambda x: x['hot_score'], reverse=True)[:top_n]
        return sorted_plates


    def get_plate_stocks(self, plate_code: str) -> List[str]:
        """
        获取板块成分股列表
        :param plate_code: 板块代码
        :return: 股票代码列表
        """
        cache = self._get_cache()

        if 'plate_stocks' in cache and plate_code in cache['plate_stocks']:
            plate_cache = cache['plate_stocks'][plate_code]
            if time.time() - plate_cache.get('update_time', 0) < self.PLATE_CACHE_EXPIRE:
                return plate_cache['stocks']

        if self.offline_mode:
            return []

        # 在线获取成分股
        try:
            stocks = []
            df = ak.stock_board_industry_cons_em(symbol=plate_code)
            for _, row in df.iterrows():
                stock_code = row['代码']
                # 转换为带前缀的格式
                if stock_code.startswith('6'):
                    stock_code = Config.STOCK_PREFIX_SH + stock_code
                else:
                    stock_code = Config.STOCK_PREFIX_SZ + stock_code
                stocks.append(stock_code)

            # 保存到缓存
            if 'plate_stocks' not in cache:
                cache['plate_stocks'] = {}
            cache['plate_stocks'][plate_code] = {
                'stocks': stocks,
                'update_time': time.time()
            }
            self._save_cache(cache)

            return stocks
        except Exception as e:
            self.logger.warning(f"获取板块{plate_code}成分股失败: {str(e)}")
            return []

    def _get_cache(self) -> Dict:
        """获取缓存数据，自动更新过期缓存"""
        if self._cache is not None:
            return self._cache

        try:
            with self._lock.read_lock():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)

            if time.time() - cache.get('update_time', 0) < self.CACHE_EXPIRE:
                self._cache = cache
                return cache
        except FileNotFoundError:
            pass

        if self.offline_mode:
            self._cache = {'update_time': time.time(), 'hot_plates': {}, 'plate_stocks': {}}
            return self._cache

        # 更新缓存
        cache = self._update_cache()
        self._cache = cache
        return cache

    def _update_cache(self) -> Dict:
        """更新热点板块缓存（线程安全版，仅在写入时持有锁）"""
        try:
            # 1. 无锁状态下完成所有耗时操作：API调用 + 数据计算
            df = ak.stock_board_industry_name_em()
            today = datetime.datetime.now().strftime('%Y%m%d')

            hot_plates = []
            for _, row in df.iterrows():
                rise_count = row['上涨家数']
                fall_count = row['下跌家数']
                total_count = rise_count + fall_count if (rise_count + fall_count) > 0 else 1
                rise_ratio = rise_count / total_count
                turnover = row.get('换手率', 0) / 100

                # 加权热度分数计算（涨跌幅40% + 上涨家数占比30% + 换手率30%）
                hot_score = (row['涨跌幅'] / 10) * Config.HOT_SCORE_CHANGE_WEIGHT + rise_ratio * Config.HOT_SCORE_RISE_RATIO_WEIGHT + turnover * Config.HOT_SCORE_TURNOVER_WEIGHT

                hot_plates.append({
                    'plate_code': row['板块代码'],
                    'plate_name': row['板块名称'],
                    'hot_score': hot_score,
                    'change_pct': row['涨跌幅'],
                    'rise_count': rise_count,
                    'fall_count': fall_count,
                    'turnover': row.get('换手率', 0)
                })

            # 仅在写入时持有写锁，减少锁持有时间
            with self._lock.write_lock():
                # 二次检查：避免多进程重复更新相同数据
                try:
                    with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                        existing_cache = json.load(f)

                    if 'hot_plates' in existing_cache and today in existing_cache['hot_plates']:
                        self._cache = existing_cache
                        return existing_cache
                except FileNotFoundError:
                    existing_cache = {}

                new_cache = {
                    'update_time': time.time(),
                    'hot_plates': {
                        today: hot_plates
                    },
                    'plate_stocks': {}
                }

                # 保留最近30天的热点数据
                if 'hot_plates' in existing_cache:
                    thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y%m%d')
                    for date in existing_cache['hot_plates']:
                        if date >= thirty_days_ago and date != today:
                            new_cache['hot_plates'][date] = existing_cache['hot_plates'][date]

                # 清理过期的板块成分股缓存
                if 'plate_stocks' in existing_cache:
                    new_plate_stocks = {}
                    current_time = time.time()
                    for plate_code, plate_data in existing_cache['plate_stocks'].items():
                        if current_time - plate_data.get('update_time', 0) < self.PLATE_CACHE_EXPIRE:
                            new_plate_stocks[plate_code] = plate_data
                    new_cache['plate_stocks'] = new_plate_stocks

                AtomicWriter.write_json(self.CACHE_FILE, new_cache, ensure_ascii=False, indent=2)

                self._cache = new_cache
                return new_cache

        except Exception as e:
            self.logger.warning(f"更新热点板块缓存失败: {str(e)}")
            try:
                with self._lock.read_lock():
                    with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                        cache = json.load(f)
                self._cache = cache
                return cache
            except FileNotFoundError:
                empty_cache = {'update_time': time.time(), 'hot_plates': {}, 'plate_stocks': {}}
                self._cache = empty_cache
                return empty_cache

    def _save_cache(self, cache: Dict):
        """保存缓存到文件"""
        with self._lock.write_lock():
            AtomicWriter.write_json(self.CACHE_FILE, cache, ensure_ascii=False, indent=2)

# 全局实例
hot_plate_fetcher = HotPlateFetcher()
