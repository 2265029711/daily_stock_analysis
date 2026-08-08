# -*- coding: utf-8 -*-
"""通知模块（Bark + 多渠道独立）单元测试"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_analysis.analyzer import AnalysisResult
from stock_analysis.config import Config, get_config
from stock_analysis.notification import BarkNotifier, NotificationService, send_notifications, send_text_notifications


@pytest.fixture(autouse=True)
def reset_config(monkeypatch):
    """重置配置单例，并用空值屏蔽 .env 中的真实配置"""
    for env in ('WECHAT_WEBHOOK_URL', 'BARK_DEVICE_KEY', 'BARK_SERVER_URL',
                'BARK_GROUP', 'OPENAI_API_KEY', 'STOCK_LIST'):
        monkeypatch.setenv(env, '')
    Config.reset_instance()
    yield
    Config.reset_instance()


def make_result(code='600519', name='贵州茅台', advice='买入', score=75):
    return AnalysisResult(
        code=code,
        name=name,
        sentiment_score=score,
        trend_prediction='看多',
        operation_advice=advice,
    )


# ========== BarkNotifier 基础测试 ==========

class TestBarkNotifier:

    def test_not_available_without_key(self):
        """未配置设备 Key 时不可用"""
        bark = BarkNotifier()
        assert bark.is_available() is False

    def test_available_with_key(self, monkeypatch):
        """配置设备 Key 后可用"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()
        bark = BarkNotifier()
        assert bark.is_available() is True

    def test_send_success(self, monkeypatch):
        """发送成功返回 True，URL 和 payload 正确"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()
        bark = BarkNotifier()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'code': 200, 'message': 'success'}

        with patch('stock_analysis.notification.requests.post', return_value=mock_response) as mock_post:
            ok = bark.send_to_bark('标题', '内容')

        assert ok is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == 'https://api.day.app/device-key-123'
        assert kwargs['json'] == {'title': '标题', 'body': '内容', 'group': '股票分析'}

    def test_send_custom_server_and_group(self, monkeypatch):
        """自建服务器地址和自定义分组"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        monkeypatch.setenv('BARK_SERVER_URL', 'https://bark.example.com')
        monkeypatch.setenv('BARK_GROUP', '股票警报')
        Config.reset_instance()
        bark = BarkNotifier()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'code': 200}

        with patch('stock_analysis.notification.requests.post', return_value=mock_response) as mock_post:
            bark.send_to_bark('标题', '内容')

        args, kwargs = mock_post.call_args
        assert args[0] == 'https://bark.example.com/device-key-123'
        assert kwargs['json']['group'] == '股票警报'

    def test_send_http_error(self, monkeypatch):
        """HTTP 非 200 返回 False"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()
        bark = BarkNotifier()

        mock_response = Mock()
        mock_response.status_code = 500

        with patch('stock_analysis.notification.requests.post', return_value=mock_response):
            ok = bark.send_to_bark('标题', '内容')

        assert ok is False

    def test_send_server_error_code(self, monkeypatch):
        """服务端返回错误码返回 False"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()
        bark = BarkNotifier()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'code': 500, 'message': 'error'}

        with patch('stock_analysis.notification.requests.post', return_value=mock_response):
            ok = bark.send_to_bark('标题', '内容')

        assert ok is False

    def test_send_exception(self, monkeypatch):
        """请求抛异常返回 False（不向上传播）"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()
        bark = BarkNotifier()

        with patch('stock_analysis.notification.requests.post', side_effect=Exception('网络错误')):
            ok = bark.send_to_bark('标题', '内容')

        assert ok is False

    def test_send_without_key(self):
        """未配置 Key 时不发请求直接返回 False"""
        bark = BarkNotifier()
        with patch('stock_analysis.notification.requests.post') as mock_post:
            ok = bark.send_to_bark('标题', '内容')
        assert ok is False
        mock_post.assert_not_called()


# ========== 多渠道独立分发测试 ==========

def mock_requests_factory(wechat_ok=True, bark_ok=True):
    """构造按 URL 区分响应的 requests.post mock"""
    def fake_post(url, **kwargs):
        response = Mock()
        response.status_code = 200
        if 'qyapi.weixin.qq.com' in url:
            response.json.return_value = {'errcode': 0 if wechat_ok else 40001}
        else:
            response.json.return_value = {'code': 200 if bark_ok else 500}
        return response
    return fake_post


class TestMultiChannel:

    def test_both_channels_send(self, monkeypatch):
        """企微和 Bark 同时配置时都发送"""
        monkeypatch.setenv('WECHAT_WEBHOOK_URL', 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc')
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            status = send_notifications([make_result()], title='测试')

        assert status == {'wechat': True, 'bark': True}
        assert mock_post.call_count == 2

    def test_wechat_fail_does_not_block_bark(self, monkeypatch):
        """企微失败不影响 Bark"""
        monkeypatch.setenv('WECHAT_WEBHOOK_URL', 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc')
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory(wechat_ok=False)) as mock_post:
            status = send_notifications([make_result()], title='测试')

        assert status['wechat'] is False
        assert status['bark'] is True
        assert mock_post.call_count == 2

    def test_wechat_exception_does_not_block_bark(self, monkeypatch):
        """企微抛异常不影响 Bark"""
        monkeypatch.setenv('WECHAT_WEBHOOK_URL', 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc')
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        def fake_post(url, **kwargs):
            if 'qyapi.weixin.qq.com' in url:
                raise Exception('企微连接超时')
            response = Mock()
            response.status_code = 200
            response.json.return_value = {'code': 200}
            return response

        with patch('stock_analysis.notification.requests.post', side_effect=fake_post):
            status = send_notifications([make_result()], title='测试')

        assert status['wechat'] is False
        assert status['bark'] is True

    def test_only_bark_configured(self, monkeypatch):
        """仅配置 Bark 时，只发 Bark，企微渠道跳过"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            status = send_notifications([make_result()], title='测试')

        assert status == {'bark': True}
        assert mock_post.call_count == 1
        url = mock_post.call_args[0][0]
        assert 'qyapi.weixin' not in url

    def test_only_wechat_configured(self, monkeypatch):
        """仅配置企微时，只发企微，Bark 渠道跳过"""
        monkeypatch.setenv('WECHAT_WEBHOOK_URL', 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            status = send_notifications([make_result()], title='测试')

        assert status == {'wechat': True}
        assert mock_post.call_count == 1
        url = mock_post.call_args[0][0]
        assert 'day.app' not in url

    def test_no_channel_configured(self):
        """未配置任何渠道时返回空字典，不发请求"""
        Config.reset_instance()
        with patch('stock_analysis.notification.requests.post') as mock_post:
            status = send_notifications([make_result()], title='测试')
        assert status == {}
        mock_post.assert_not_called()

    def test_send_text_notifications(self, monkeypatch):
        """文本通知分发（大盘复盘场景）"""
        monkeypatch.setenv('WECHAT_WEBHOOK_URL', 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc')
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            status = send_text_notifications('复盘报告内容', title='大盘复盘')

        assert status == {'wechat': True, 'bark': True}
        assert mock_post.call_count == 2
