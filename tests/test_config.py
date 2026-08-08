# -*- coding: utf-8 -*-
"""配置模块单元测试"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_analysis.config import Config, get_config


@pytest.fixture(autouse=True)
def reset_config(monkeypatch):
    """每个测试前重置配置单例，并用空值屏蔽 .env 中的真实配置"""
    for env in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL',
                'BARK_DEVICE_KEY', 'BARK_SERVER_URL', 'BARK_GROUP',
                'WECHAT_WEBHOOK_URL', 'STOCK_LIST', 'TAVILY_API_KEYS',
                'TAVILY_API_KEY_1', 'TAVILY_API_KEY_2', 'TAVILY_API_KEY_3',
                'SERPAPI_KEYS'):
        monkeypatch.setenv(env, '')
    # 数值型配置设为文档默认值（空串会导致 float/int 解析报错）
    monkeypatch.setenv('OPENAI_REQUEST_DELAY', '2.0')
    monkeypatch.setenv('OPENAI_MAX_RETRIES', '5')
    monkeypatch.setenv('OPENAI_RETRY_DELAY', '5.0')
    Config.reset_instance()
    yield
    Config.reset_instance()


def test_config_no_gemini_fields():
    """配置对象不再包含任何 Gemini 字段"""
    config = get_config()
    for field in ('gemini_api_key', 'gemini_model', 'gemini_model_fallback',
                  'gemini_request_delay', 'gemini_max_retries', 'gemini_retry_delay'):
        assert not hasattr(config, field), f"配置不应包含 Gemini 字段: {field}"


def test_openai_fields_defaults(monkeypatch):
    """OpenAI 配置字段从环境变量加载，未设置时使用默认值"""
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key-123456')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
    monkeypatch.setenv('OPENAI_MODEL', 'deepseek-chat')
    config = get_config()
    assert config.openai_api_key == 'sk-test-key-123456'
    assert config.openai_base_url == 'https://api.deepseek.com/v1'
    assert config.openai_model == 'deepseek-chat'
    assert config.openai_request_delay == 2.0
    assert config.openai_max_retries == 5
    assert config.openai_retry_delay == 5.0


def test_openai_retry_config_custom(monkeypatch):
    """OpenAI 流控参数可自定义"""
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key-123456')
    monkeypatch.setenv('OPENAI_REQUEST_DELAY', '1.5')
    monkeypatch.setenv('OPENAI_MAX_RETRIES', '3')
    monkeypatch.setenv('OPENAI_RETRY_DELAY', '2.0')
    config = get_config()
    assert config.openai_request_delay == 1.5
    assert config.openai_max_retries == 3
    assert config.openai_retry_delay == 2.0


def test_openai_model_not_configured():
    """OPENAI_MODEL 未配置时为 None（不预设默认模型）"""
    config = get_config()
    assert config.openai_model is None


def test_bark_fields_defaults(monkeypatch):
    """Bark 配置字段默认值"""
    config = get_config()
    assert config.bark_device_key is None
    assert config.bark_server_url == 'https://api.day.app'
    assert config.bark_group == '股票分析'


def test_bark_fields_custom(monkeypatch):
    """Bark 配置字段从环境变量加载"""
    monkeypatch.setenv('BARK_DEVICE_KEY', 'my-device-key')
    monkeypatch.setenv('BARK_SERVER_URL', 'https://bark.example.com')
    monkeypatch.setenv('BARK_GROUP', '股票警报')
    config = get_config()
    assert config.bark_device_key == 'my-device-key'
    assert config.bark_server_url == 'https://bark.example.com'
    assert config.bark_group == '股票警报'


def test_validate_without_openai_key():
    """未配置 OpenAI Key 时 validate() 给出警告"""
    config = get_config()
    warnings = config.validate()
    assert any('AI 分析功能将不可用' in w for w in warnings)


def test_validate_with_openai_key(monkeypatch):
    """只配置 Key 时，base_url 和 model 缺失均给出警告"""
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key-123456')
    config = get_config()
    warnings = config.validate()
    assert not any('AI 分析功能将不可用' in w for w in warnings)
    assert any('OPENAI_BASE_URL' in w for w in warnings)
    assert any('OPENAI_MODEL' in w for w in warnings)


def test_validate_full_openai_config(monkeypatch):
    """三项全部配置后不再告警 AI 配置缺失"""
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key-123456')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
    monkeypatch.setenv('OPENAI_MODEL', 'deepseek-chat')
    config = get_config()
    warnings = config.validate()
    assert not any('OPENAI_BASE_URL' in w for w in warnings)
    assert not any('OPENAI_MODEL' in w for w in warnings)
    assert not any('AI 分析功能将不可用' in w for w in warnings)


def test_validate_notification_warning():
    """未配置任何通知渠道时给出警告"""
    config = get_config()
    warnings = config.validate()
    assert any('通知渠道' in w for w in warnings)


def test_validate_bark_channel_ok(monkeypatch):
    """配置 Bark 后通知渠道警告消失"""
    monkeypatch.setenv('BARK_DEVICE_KEY', 'my-device-key')
    config = get_config()
    warnings = config.validate()
    assert not any('通知渠道' in w for w in warnings)


def test_tavily_keys_comma_separated(monkeypatch):
    """逗号分隔格式兼容"""
    monkeypatch.setenv('TAVILY_API_KEYS', 'tvly-key1,tvly-key2')
    config = get_config()
    assert config.tavily_api_keys == ['tvly-key1', 'tvly-key2']


def test_tavily_keys_one_per_line(monkeypatch):
    """一个 key 一行的格式（TAVILY_API_KEY_N 聚合）"""
    monkeypatch.setenv('TAVILY_API_KEY_1', 'tvly-key-a')
    monkeypatch.setenv('TAVILY_API_KEY_2', 'tvly-key-b')
    monkeypatch.setenv('TAVILY_API_KEY_3', 'tvly-key-c')
    config = get_config()
    assert config.tavily_api_keys == ['tvly-key-a', 'tvly-key-b', 'tvly-key-c']


def test_tavily_keys_mixed_formats(monkeypatch):
    """两种格式混合时合并去重"""
    monkeypatch.setenv('TAVILY_API_KEYS', 'tvly-key1,tvly-key2')
    monkeypatch.setenv('TAVILY_API_KEY_2', 'tvly-key2')
    monkeypatch.setenv('TAVILY_API_KEY_3', 'tvly-key3')
    config = get_config()
    assert config.tavily_api_keys == ['tvly-key1', 'tvly-key2', 'tvly-key3']
