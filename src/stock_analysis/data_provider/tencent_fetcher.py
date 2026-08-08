# -*- coding: utf-8 -*-
"""
===================================
TencentFetcher - 备用数据源 (Priority 2)
===================================

数据来源：腾讯行情 API（免费、无需 Token、HTTP 无状态支持并发）
特点：
- 日线 K 线：ifzq.gtimg.cn/appstock/app/fqkline/get（前复权）
- 实时行情：qt.gtimg.cn（量比/换手/PE/PB/市值）
- 稳定性好：不依赖东财、无登录态、天然支持多线程并发

定位：AkShare（东财）不可用时的首选兜底，优先于 Tushare / Baostock
"""

import logging
import time
from typing import Optional, Tuple

import pandas as pd
import requests

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS

logger = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# 腾讯 K 线接口（单次最多约 320 条）
KLINE_URL = "https://ifzq.gtimg.cn/appstock/app/fqkline/get"


def to_tencent_symbol(stock_code: str) -> str:
    """
    转换股票代码为腾讯格式
    
    - 6xxxxx -> sh6xxxxx（沪市 A 股/科创/ETF）
    - 0xxxxx / 3xxxxx -> szxxxxxx（深市）
    - 5xxxxx -> sh5xxxxx（沪市基金/ETF）
    - 1xxxxx -> sz1xxxxx（深市基金/ETF）
    - 4xxxxx / 8xxxxx -> bjxxxxxx（北交所）
    """
    if stock_code.startswith('6') or stock_code.startswith('5'):
        return f"sh{stock_code}"
    if stock_code.startswith(('0', '3', '1')):
        return f"sz{stock_code}"
    if stock_code.startswith(('4', '8')):
        return f"bj{stock_code}"
    return f"sh{stock_code}"


class TencentFetcher(BaseFetcher):
    """
    腾讯行情数据源实现
    
    优先级：2（AkShare 之后，Tushare 之前）
    数据来源：腾讯行情 API（免费、无需 Token）
    
    关键策略：
    - HTTP 无状态接口，支持多线程并发（不依赖登录态）
    - 失败快速重试一次
    """
    
    name = "TencentFetcher"
    priority = 2
    
    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": UA})
    
    def _fetch_raw_data(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        从腾讯获取日线 K 线数据（前复权）
        
        API: https://ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start},{end},320,qfq
        
        返回行格式：[日期, 开盘, 收盘, 最高, 最低, 成交量(手)]
        """
        symbol = to_tencent_symbol(stock_code)
        
        # 腾讯接口最多返回约 320 条，默认拉满
        param = f"{symbol},day,{start_date or ''},{end_date or ''},320,qfq"
        
        for attempt in range(2):
            try:
                logger.info(f"[API调用] 腾讯日线: {symbol} ({start_date} ~ {end_date})")
                resp = self._session.get(KLINE_URL, params={"param": param}, timeout=15)
                resp.raise_for_status()
                
                data = resp.json()
                stock_data = data.get('data', {}).get(symbol, {})
                # 前复权优先，其次不复权
                kline = stock_data.get('qfqday') or stock_data.get('day') or []
                
                if not kline:
                    raise DataFetchError(f"腾讯返回空数据: {symbol}")
                
                # 部分行可能带额外字段（第7列为均线等），只取前6列
                kline = [row[:6] for row in kline if len(row) >= 6]
                if not kline:
                    raise DataFetchError(f"腾讯返回数据格式异常: {symbol}")
                
                df = pd.DataFrame(kline, columns=['date', 'open', 'close', 'high', 'low', 'volume'])
                
                # 按日期范围过滤（接口可能返回超出范围的数据）
                if start_date:
                    df = df[df['date'] >= start_date]
                if end_date:
                    df = df[df['date'] <= end_date]
                
                logger.info(f"[API返回] 腾讯日线 {stock_code} 成功: {len(df)} 行, "
                           f"{df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
                return df
                
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"[腾讯] 第 1 次请求失败，重试: {e}")
                    time.sleep(1.0)
                else:
                    raise DataFetchError(f"腾讯获取 {stock_code} 失败: {e}") from e
        
        raise DataFetchError(f"腾讯获取 {stock_code} 失败")
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化腾讯数据
        
        腾讯返回列名已是标准列，直接整理格式
        """
        df = df.copy()
        
        # 确保列存在
        for col in ['date', 'open', 'high', 'low', 'close', 'volume']:
            if col not in df.columns:
                df[col] = None
        
        # 数值转换
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 只保留标准列
        keep_cols = ['code'] + STANDARD_COLUMNS
        df['code'] = stock_code
        existing_cols = [col for col in keep_cols if col in df.columns]
        
        return df[existing_cols]
