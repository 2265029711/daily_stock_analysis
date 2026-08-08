# -*- coding: utf-8 -*-
"""多用户推送配置单元测试"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_analysis.push_config import PushConfig, PushUser, _resolve_env
from stock_analysis.config import Config, get_config


@pytest.fixture(autouse=True)
def reset_config(monkeypatch):
    """屏蔽 .env 真实配置"""
    for env in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL',
                'BARK_DEVICE_KEY', 'BARK_SERVER_URL', 'BARK_GROUP',
                'WECHAT_WEBHOOK_URL', 'STOCK_LIST', 'TAVILY_API_KEYS',
                'BARK_KEY_USER_A', 'BARK_KEY_USER_B', 'BARK_KEY_USER_C'):
        monkeypatch.setenv(env, '')
    Config.reset_instance()
    yield
    Config.reset_instance()


SAMPLE_YAML = """
users:
  - name: 用户A-大盘
    device_key: ${BARK_KEY_USER_A}
    group: 大盘走势
    push_market: true
    stocks: []

  - name: 用户B-个股
    device_key: key-b-direct
    group: 个股分析
    push_market: false
    stocks: ['600519', '300750']

  - name: 用户C-全部
    device_key: ${BARK_KEY_USER_C}
    push_market: true
    stocks: all
"""


def write_config(tmp_path, content):
    path = tmp_path / 'push_config.yaml'
    path.write_text(content, encoding='utf-8')
    return path


class TestPushConfigLoad:

    def test_load_missing_file(self, tmp_path):
        """配置文件不存在时返回空配置"""
        cfg = PushConfig.load(tmp_path / 'nonexist.yaml')
        assert cfg.users == []
        assert cfg.is_configured is False

    def test_load_invalid_yaml(self, tmp_path):
        """YAML 格式错误时返回空配置"""
        path = write_config(tmp_path, "users: [unclosed")
        cfg = PushConfig.load(path)
        assert cfg.users == []

    def test_load_basic_fields(self, tmp_path, monkeypatch):
        """基本字段解析"""
        monkeypatch.setenv('BARK_KEY_USER_A', 'key-a')
        monkeypatch.setenv('BARK_KEY_USER_C', 'key-c')
        path = write_config(tmp_path, SAMPLE_YAML)
        cfg = PushConfig.load(path)
        assert len(cfg.users) == 3

        user_a = cfg.users[0]
        assert user_a.name == '用户A-大盘'
        assert user_a.device_key == 'key-a'
        assert user_a.push_market is True
        assert user_a.stocks == []
        assert user_a.wants_stocks is False

        user_b = cfg.users[1]
        assert user_b.device_key == 'key-b-direct'
        assert user_b.stocks == ['600519', '300750']
        assert user_b.wants_stocks is True

        user_c = cfg.users[2]
        assert user_c.all_stocks is True
        assert user_c.wants_stocks is True

    def test_env_placeholder_resolution(self, tmp_path, monkeypatch):
        """${ENV} 占位符解析为环境变量值"""
        monkeypatch.setenv('BARK_KEY_USER_A', 'resolved-key-a')
        path = write_config(tmp_path, SAMPLE_YAML)
        cfg = PushConfig.load(path)
        assert cfg.users[0].device_key == 'resolved-key-a'

    def test_missing_env_user_skipped(self, tmp_path, monkeypatch):
        """占位符对应的环境变量缺失时，该用户被跳过"""
        monkeypatch.setenv('BARK_KEY_USER_A', '')
        path = write_config(tmp_path, SAMPLE_YAML)
        cfg = PushConfig.load(path)
        # 用户A（占位符未解析）+ 用户C（占位符未解析）被跳过，只剩用户B
        names = [u.name for u in cfg.users]
        assert names == ['用户B-个股']

    def test_is_configured(self, tmp_path, monkeypatch):
        """至少一个有效用户时 is_configured 为 True"""
        monkeypatch.setenv('BARK_KEY_USER_A', 'key-a')
        path = write_config(tmp_path, SAMPLE_YAML)
        cfg = PushConfig.load(path)
        assert cfg.is_configured is True

    def test_resolve_env_plain_text(self):
        """无占位符的文本原样返回"""
        assert _resolve_env('abc-123', []) == 'abc-123'

    def test_resolve_env_missing_recorded(self, monkeypatch):
        """缺失的环境变量被记录"""
        monkeypatch.delenv('MISSING_VAR', raising=False)
        missing = []
        result = _resolve_env('${MISSING_VAR}xxx', missing)
        assert result == 'xxx'
        assert 'MISSING_VAR' in missing


class TestPushUserStocks:

    def test_get_user_stocks_all(self, tmp_path, monkeypatch):
        """stocks: all 返回全局列表"""
        monkeypatch.setenv('BARK_KEY_USER_C', 'key-c')
        path = write_config(tmp_path, SAMPLE_YAML)
        cfg = PushConfig.load(path)
        user_c = cfg.users[1]  # 用户C（占位符已解析）
        assert cfg.get_user_stocks(user_c, ['600519', '000001']) == ['600519', '000001']

    def test_get_user_stocks_specific(self, tmp_path, monkeypatch):
        """stocks 指定列表原样返回（支持全局 STOCK_LIST 之外的股票）"""
        monkeypatch.setenv('BARK_KEY_USER_A', 'key-a')
        path = write_config(tmp_path, SAMPLE_YAML)
        cfg = PushConfig.load(path)
        user_b = cfg.users[1]
        result = cfg.get_user_stocks(user_b, ['000001'])
        # 不限制在全局列表内：600519/300750 直接返回
        assert result == ['600519', '300750']

    def test_get_requested_stocks_merge(self, tmp_path, monkeypatch):
        """汇总所有用户股票（去重，含全局之外的代码）"""
        monkeypatch.setenv('BARK_KEY_USER_A', 'key-a')
        monkeypatch.setenv('BARK_KEY_USER_C', 'key-c')
        path = write_config(tmp_path, SAMPLE_YAML)
        cfg = PushConfig.load(path)
        requested = cfg.get_requested_stocks(['000001'])
        # 用户B 的 600519/300750 + 用户C 的 all(=000001)
        assert set(requested) == {'600519', '300750', '000001'}


class TestResolveAnalysisStocks:

    def test_default_returns_all(self, tmp_path, monkeypatch):
        """默认（非按需）返回全局 STOCK_LIST"""
        monkeypatch.setenv('BARK_KEY_USER_A', 'key-a')
        monkeypatch.setenv('BARK_KEY_USER_C', 'key-c')
        path = write_config(tmp_path, SAMPLE_YAML)
        cfg = PushConfig.load(path)
        result = cfg.resolve_analysis_stocks(['600519', '300750', '002594'])
        assert result == ['600519', '300750', '002594']

    def test_requested_only_returns_user_union(self, tmp_path, monkeypatch):
        """按需分析只返回用户请求的股票并集"""
        monkeypatch.setenv('BARK_KEY_USER_A', 'key-a')
        monkeypatch.setenv('BARK_KEY_USER_C', 'key-c')
        path = write_config(tmp_path, SAMPLE_YAML)
        cfg = PushConfig.load(path)
        # 用户B: 600519,300750；用户C: all(全局)
        result = cfg.resolve_analysis_stocks(['600519', '300750', '002594'], requested_only=True)
        assert set(result) == {'600519', '300750', '002594'}

    def test_requested_only_with_specific_users(self, tmp_path, monkeypatch):
        """按需分析时只分析用户明确指定的股票（不含全局多余的）"""
        yaml = """
users:
  - name: 用户B
    device_key: key-b
    stocks: ['600664', '000725']
"""
        path = write_config(tmp_path, yaml)
        cfg = PushConfig.load(path)
        result = cfg.resolve_analysis_stocks(['600519', '300750', '002594'], requested_only=True)
        assert result == ['600664', '000725']

    def test_requested_only_no_stock_users(self, tmp_path, monkeypatch):
        """按需分析时所有用户都不要个股 → 返回空（跳过个股分析）"""
        yaml = """
users:
  - name: 用户A
    device_key: key-a
    push_market: true
    stocks: []
"""
        path = write_config(tmp_path, yaml)
        cfg = PushConfig.load(path)
        result = cfg.resolve_analysis_stocks(['600519', '300750'], requested_only=True)
        assert result == []

    def test_requested_only_no_config(self, tmp_path):
        """按需分析但无配置用户 → 回退全局列表"""
        cfg = PushConfig.load(tmp_path / 'nonexist.yaml')
        result = cfg.resolve_analysis_stocks(['600519'], requested_only=True)
        assert result == ['600519']


class TestPushConfigValidate:

    def test_validate_bad_code_format(self, tmp_path, monkeypatch):
        """股票代码格式非法时给出警告"""
        monkeypatch.setenv('BARK_KEY_USER_A', 'key-a')
        yaml = """
users:
  - name: 用户X
    device_key: key-x
    stocks: ['12345', 'abcdef', '600519']
"""
        path = write_config(tmp_path, yaml)
        cfg = PushConfig.load(path)
        warnings = cfg.validate(['600519'])
        assert any('12345' in w for w in warnings)
        assert any('abcdef' in w for w in warnings)
        assert not any('600519' in w for w in warnings)

    def test_validate_leading_zero_code(self, tmp_path, monkeypatch):
        """带前导零的代码（'000725' 引号字符串）不被误判"""
        monkeypatch.setenv('BARK_KEY_USER_A', 'key-a')
        yaml = """
users:
  - name: 用户X
    device_key: key-x
    stocks: ['000725']
"""
        path = write_config(tmp_path, yaml)
        cfg = PushConfig.load(path)
        warnings = cfg.validate(['600519'])
        assert not any('000725' in w for w in warnings)

    def test_validate_market_only_user(self, tmp_path, monkeypatch):
        """只收大盘的用户给出提示（非错误）"""
        monkeypatch.setenv('BARK_KEY_USER_A', 'key-a')
        path = write_config(tmp_path, SAMPLE_YAML)
        cfg = PushConfig.load(path)
        warnings = cfg.validate(['600519'])
        assert any('用户A-大盘' in w for w in warnings)
