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
from config import Config
from logger import GlobalLogger

class HotPlateFetcher:
    """热点板块数据获取器"""

    # 缓存文件路径
    CACHE_FILE = os.path.join(Config.SAVED_DATA_DIR, 'hot_plates_cache.json')
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
        self._lock = FileRWLock(self.CACHE_FILE + '.lock')
        self.logger = GlobalLogger.get_logger(__name__)

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

        # 缓存中存在且未过期则直接返回
        if 'plate_stocks' in cache and plate_code in cache['plate_stocks']:
            plate_cache = cache['plate_stocks'][plate_code]
            if time.time() - plate_cache.get('update_time', 0) < self.PLATE_CACHE_EXPIRE:
                return plate_cache['stocks']

        # 离线模式下如果没有缓存则返回空
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
                    stock_code = 'sh' + stock_code
                else:
                    stock_code = 'sz' + stock_code
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
        # 内存缓存存在直接返回
        if self._cache is not None:
            return self._cache

        # 文件缓存存在且未过期
        if os.path.exists(self.CACHE_FILE):
            with self._lock.read_lock():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)

            # 检查是否过期
            if time.time() - cache.get('update_time', 0) < self.CACHE_EXPIRE:
                self._cache = cache
                return cache

        # 离线模式下返回空缓存
        if self.offline_mode:
            self._cache = {'update_time': time.time(), 'hot_plates': {}, 'plate_stocks': {}}
            return self._cache

        # 更新缓存
        cache = self._update_cache()
        self._cache = cache
        return cache

    def _update_cache(self) -> Dict:
        """更新热点板块缓存（线程安全版，整个更新流程在写锁保护下）"""
        # 整个更新流程加写锁，避免多进程同时更新冲突
        with self._lock.write_lock():
            try:
                # 获取当前热点板块
                df = ak.stock_board_industry_name_em()
                today = datetime.datetime.now().strftime('%Y%m%d')

                # 格式化数据
                hot_plates = []
                for _, row in df.iterrows():
                    # 计算加权热度分数：涨跌幅(40%) + 上涨家数占比(30%) + 换手率(30%)
                    rise_count = row['上涨家数']
                    fall_count = row['下跌家数']
                    total_count = rise_count + fall_count if (rise_count + fall_count) > 0 else 1
                    rise_ratio = rise_count / total_count
                    turnover = row.get('换手率', 0) / 100  # 转换为小数

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

                # 构建新缓存
                new_cache = {
                    'update_time': time.time(),
                    'hot_plates': {
                        today: hot_plates
                    },
                    'plate_stocks': {}
                }

                # 合并旧缓存数据（保留最近30天的数据）
                if os.path.exists(self.CACHE_FILE):
                    with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                        old_cache = json.load(f)

                    if 'hot_plates' in old_cache:
                        # 只保留最近30天的数据
                        thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y%m%d')
                        for date in old_cache['hot_plates']:
                            if date >= thirty_days_ago and date != today:
                                new_cache['hot_plates'][date] = old_cache['hot_plates'][date]

                    if 'plate_stocks' in old_cache:
                        new_cache['plate_stocks'] = old_cache['plate_stocks']

                # 直接写入缓存，不需要再调用_save_cache（已经在写锁里了）
                # 先写入临时文件，再替换，避免文件损坏
                temp_file = self.CACHE_FILE + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(new_cache, f, ensure_ascii=False, indent=2)

                if os.path.exists(self.CACHE_FILE):
                    os.remove(self.CACHE_FILE)
                os.rename(temp_file, self.CACHE_FILE)

                return new_cache

            except Exception as e:
                self.logger.warning(f"更新热点板块缓存失败: {str(e)}")
                # 失败则返回旧缓存或空缓存
                if os.path.exists(self.CACHE_FILE):
                    with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                        return json.load(f)
                return {'update_time': time.time(), 'hot_plates': {}, 'plate_stocks': {}}

    def _save_cache(self, cache: Dict):
        """保存缓存到文件"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)

        with self._lock.write_lock():
            # 先写入临时文件，再替换，避免文件损坏
            temp_file = self.CACHE_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

            if os.path.exists(self.CACHE_FILE):
                os.remove(self.CACHE_FILE)
            os.rename(temp_file, self.CACHE_FILE)

# 全局实例
hot_plate_fetcher = HotPlateFetcher()
