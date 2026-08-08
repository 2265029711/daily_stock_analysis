# -*- coding: utf-8 -*-
"""腾讯数据源代码转换单元测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_analysis.data_provider.tencent_fetcher import to_tencent_symbol


class TestTencentSymbol:

    def test_sh_stock(self):
        """沪市 A 股"""
        assert to_tencent_symbol('600519') == 'sh600519'
        assert to_tencent_symbol('688981') == 'sh688981'

    def test_sz_stock(self):
        """深市 A 股/创业板"""
        assert to_tencent_symbol('000725') == 'sz000725'
        assert to_tencent_symbol('300750') == 'sz300750'

    def test_sh_etf(self):
        """沪市 ETF（5 开头）"""
        assert to_tencent_symbol('516350') == 'sh516350'

    def test_sz_etf(self):
        """深市基金（1 开头）"""
        assert to_tencent_symbol('159915') == 'sz159915'

    def test_bj(self):
        """北交所"""
        assert to_tencent_symbol('430047') == 'bj430047'
