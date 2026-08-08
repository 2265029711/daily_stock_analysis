# -*- coding: utf-8 -*-
"""搜索服务：配额冷却 + 多 Key 轮换单元测试"""
import json
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import stock_analysis.search_service as ss
from stock_analysis.search_service import SearchResponse, TavilySearchProvider


@pytest.fixture(autouse=True)
def isolate_state_file(monkeypatch, tmp_path):
    """隔离配额状态文件到临时目录"""
    monkeypatch.setattr(ss, 'SEARCH_STATE_FILE', tmp_path / 'state.json')
    yield


def make_success_response(results=3):
    return SearchResponse(query='测试', results=[Mock() for _ in range(results)],
                          provider='Tavily', success=True)


def make_fail_response(error_msg):
    return SearchResponse(query='测试', results=[], provider='Tavily',
                          success=False, error_message=error_msg)


class TestQuotaRotation:

    def test_quota_error_marks_cooldown(self, monkeypatch):
        """配额用尽错误 → key 进入冷却并持久化"""
        provider = TavilySearchProvider(['key1', 'key2'])
        provider._do_search = Mock(side_effect=[
            make_fail_response('API key quota exceeded - monthly limit reached'),
            make_success_response(),
        ])

        # 第一次调用：key1 配额错误
        resp1 = provider.search('q1')
        assert resp1.success is False
        # key1 进入冷却
        assert provider._quota_until.get('key1', 0) > time.time()

        # 状态文件已写入
        state = json.loads(ss.SEARCH_STATE_FILE.read_text(encoding='utf-8'))
        assert 'Tavily' in state
        assert 'key1' in state['Tavily']

        # 第二次调用：跳过 key1，使用 key2
        resp2 = provider.search('q2')
        assert resp2.success is True
        assert provider._key_usage.get('key2', 0) == 1

    def test_normal_error_not_cooldown(self, monkeypatch):
        """普通网络错误不进入配额冷却（只计错误次数）"""
        provider = TavilySearchProvider(['key1', 'key2'])
        provider._do_search = Mock(side_effect=[
            make_fail_response('Connection timeout'),
            make_success_response(),
        ])

        provider.search('q1')
        # key1 不进入冷却
        assert 'key1' not in provider._quota_until
        # 错误计数 +1
        assert provider._key_errors['key1'] == 1

    def test_all_keys_in_cooldown_returns_none(self, monkeypatch):
        """所有 key 均在冷却时快速失败（返回 None，不浪费请求）"""
        provider = TavilySearchProvider(['key1', 'key2'])
        # 手动设置两个 key 都在冷却
        provider._quota_until = {'key1': time.time() + 86400, 'key2': time.time() + 86400}
        provider._do_search = Mock()

        key = provider._get_next_key()
        assert key is None
        provider._do_search.assert_not_called()

    def test_cooldown_expiry_recovers(self, monkeypatch):
        """冷却到期后 key 自动恢复使用"""
        provider = TavilySearchProvider(['key1'])
        # key1 冷却已在过去到期
        provider._quota_until = {'key1': time.time() - 1}
        key = provider._get_next_key()
        assert key == 'key1'

    def test_quota_state_loaded_from_file(self, monkeypatch):
        """冷却状态从文件加载（新实例跳过冷却中的 key）"""
        # 先写一个 key1 冷却中的状态文件
        ss.SEARCH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        ss.SEARCH_STATE_FILE.write_text(json.dumps({
            'Tavily': {'key1': time.time() + 86400}
        }), encoding='utf-8')

        provider = TavilySearchProvider(['key1', 'key2'])
        assert provider._quota_until.get('key1', 0) > time.time()
        # key1 被跳过，返回 key2
        assert provider._get_next_key() == 'key2'

    def test_is_quota_error_detection(self):
        """配额类错误关键词识别"""
        assert ss.BaseSearchProvider._is_quota_error('API key quota exceeded') is True
        assert ss.BaseSearchProvider._is_quota_error('429 Too Many Requests') is True
        assert ss.BaseSearchProvider._is_quota_error('monthly limit reached') is True
        assert ss.BaseSearchProvider._is_quota_error('Payment Required 402') is True
        assert ss.BaseSearchProvider._is_quota_error('Connection timeout') is False
        assert ss.BaseSearchProvider._is_quota_error('') is False
