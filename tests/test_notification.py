# -*- coding: utf-8 -*-
"""通知模块（Bark + 多渠道独立）单元测试"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_analysis.analyzer import AnalysisResult
from stock_analysis.config import Config, get_config
from stock_analysis.notification import (
    BarkNotifier,
    NotificationService,
    send_notifications,
    send_text_notifications,
    send_user_notifications,
)


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


def make_full_result(code='600519', name='贵州茅台'):
    """构造带完整数据（实时行情/趋势/情报/结论）的分析结果"""
    result = AnalysisResult(
        code=code,
        name=name,
        sentiment_score=75,
        trend_prediction='看多',
        operation_advice='买入',
        buy_reason='缩量回踩MA5支撑，乖离率安全，多头排列',
        risk_warning='注意解禁风险',
        dashboard={
            'core_conclusion': {
                'one_sentence': '回踩MA5可分批介入',
                'position_advice': {
                    'no_position': '空仓者可在回踩时建仓',
                    'has_position': '持仓者可继续持有',
                },
            },
            'intelligence': {
                'latest_news': '茅台发布一季报经营数据公告',
                'risk_alerts': ['风险：大额解禁'],
                'positive_catalysts': ['利好：业绩预增'],
            },
            'battle_plan': {
                'sniper_points': {
                    'ideal_buy': '1300元',
                    'stop_loss': '1280元',
                    'take_profit': '1400元',
                },
            },
        },
        realtime_data={
            'price': 1309.22,
            'change_pct': 0.05,
            'volume_ratio': 0.63,
            'turnover_rate': 0.2,
            'pe_ratio': 19.79,
            'pb_ratio': 7.03,
            'total_mv': 1.636632e12,
            'circ_mv': 1.636632e12,
        },
        trend_data={
            'ma_alignment': '多头排列',
            'bias_ma5': -0.46,
            'signal_score': 68,
            'buy_signal': '持有',
        },
    )
    return result


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


# ========== Bark 推送内容测试（数据先行，LLM 结论收尾） ==========

class TestBarkContent:

    def test_content_contains_realtime_data(self, monkeypatch):
        """推送内容包含实时行情数据"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            send_notifications([make_full_result()], title='测试')

        body = mock_post.call_args.kwargs['json']['body']
        assert '实时行情' in body
        assert '1309.22' in body
        assert '量比 0.63' in body
        assert '换手 0.2%' in body
        assert 'PE 19.79' in body
        assert 'PB 7.03' in body

    def test_content_contains_trend_and_news(self, monkeypatch):
        """推送内容包含技术面和情报摘要"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            send_notifications([make_full_result()], title='测试')

        body = mock_post.call_args.kwargs['json']['body']
        assert '技术面' in body
        assert '多头排列' in body
        assert '乖离' in body
        assert '新闻' in body or '茅台' in body
        assert '风险' in body
        assert '利好' in body

    def test_llm_conclusion_after_data(self, monkeypatch):
        """LLM 结论出现在数据之后（数据先行，结论收尾）"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            send_notifications([make_full_result()], title='测试')

        body = mock_post.call_args.kwargs['json']['body']
        assert '结论' in body
        assert '理由' in body
        # 结论行在实时行情行之后
        assert body.index('结论') > body.index('实时行情')
        # 理由包含具体操作依据
        assert '理由' in body

    def test_content_contains_sniper_points(self, monkeypatch):
        """推送内容包含狙击点位（完整描述）"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            send_notifications([make_full_result()], title='测试')

        body = mock_post.call_args.kwargs['json']['body']
        assert '买: 1300元' in body  # 理想买入点
        assert '损: 1280元' in body  # 止损
        assert '标: 1400元' in body  # 目标

    def test_sniper_points_full_description(self, monkeypatch):
        """点位输出完整描述（不做逐行截断）"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        result = make_full_result()
        result.dashboard['battle_plan']['sniper_points'] = {
            'ideal_buy': '理想买入点：383.89元附近（MA5附近，乖离率0.47%）',
            'stop_loss': '止损位：378.00元（跌破MA20支撑）',
            'take_profit': '目标位：400.00元（整数关口+前高）',
        }

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            send_notifications([result], title='测试')

        body = mock_post.call_args.kwargs['json']['body']
        # 完整描述原样输出，不再截断、不出现省略号
        assert '买: 理想买入点：383.89元附近（MA5附近，乖离率0.47%）' in body
        assert '损: 止损位：378.00元（跌破MA20支撑）' in body
        assert '标: 目标位：400.00元（整数关口+前高）' in body

    def test_no_ellipsis_in_normal_content(self, monkeypatch):
        """正常内容不出现省略号（...）"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            send_notifications([make_full_result()], title='测试')

        body = mock_post.call_args.kwargs['json']['body']
        assert '...' not in body

    def test_content_without_data_still_works(self, monkeypatch):
        """无实时数据时内容正常生成（不报错）"""
        monkeypatch.setenv('BARK_DEVICE_KEY', 'device-key-123')
        Config.reset_instance()

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            send_notifications([make_result()], title='测试')

        body = mock_post.call_args.kwargs['json']['body']
        assert '贵州茅台' in body
        assert '买入' in body


# ========== 多用户推送测试（push_config.yaml） ==========

def make_push_config_file(tmp_path, yaml_content):
    import yaml
    from stock_analysis import push_config as pc
    path = tmp_path / 'push_config.yaml'
    path.write_text(yaml_content, encoding='utf-8')
    # 让 push_config 模块指向测试文件
    monkeypatch_target = 'stock_analysis.push_config.DEFAULT_CONFIG_PATH'
    return path


class TestMultiUserPush:

    def test_two_users_receive_filtered_content(self, monkeypatch, tmp_path):
        """两个用户各自收到过滤后的内容，互不影响"""
        # 用户B(股1) 和 用户C(股2)
        yaml = """
users:
  - name: 用户B
    device_key: key-b
    group: 个股分析
    stocks: [600519]
  - name: 用户C
    device_key: key-c
    group: 个股分析
    stocks: [300750]
"""
        path = tmp_path / 'push_config.yaml'
        path.write_text(yaml, encoding='utf-8')
        monkeypatch.setattr('stock_analysis.push_config.DEFAULT_CONFIG_PATH', path)
        monkeypatch.setenv('STOCK_LIST', '600519,300750')

        result_maotai = make_full_result()
        result_catl = make_full_result(code='300750', name='宁德时代')
        result_catl.realtime_data['price'] = 388.07
        result_catl.dashboard['core_conclusion']['one_sentence'] = '宁德结论'

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            status = send_user_notifications([result_maotai, result_catl], title='测试')

        assert status == {'用户B': True, '用户C': True}
        # 两次请求：两个不同的 device key
        urls = [call.args[0] for call in mock_post.call_args_list]
        assert len(urls) == 2
        assert 'key-b' in urls[0]
        assert 'key-c' in urls[1]

        # 用户B 只收到茅台，用户C 只收到宁德
        bodies = [call.kwargs['json']['body'] for call in mock_post.call_args_list]
        assert '贵州茅台' in bodies[0]
        assert '宁德时代' not in bodies[0]
        assert '宁德时代' in bodies[1]
        assert '贵州茅台' not in bodies[1]

    def test_market_only_user(self, monkeypatch, tmp_path):
        """只收大盘的用户收到复盘报告"""
        yaml = """
users:
  - name: 用户A
    device_key: key-a
    group: 大盘走势
    push_market: true
    stocks: []
"""
        path = tmp_path / 'push_config.yaml'
        path.write_text(yaml, encoding='utf-8')
        monkeypatch.setattr('stock_analysis.push_config.DEFAULT_CONFIG_PATH', path)

        with patch('stock_analysis.notification.requests.post', side_effect=mock_requests_factory()) as mock_post:
            status = send_user_notifications([make_full_result()], market_report='大盘复盘内容')

        assert status == {'用户A': True}
        assert mock_post.call_count == 1
        body = mock_post.call_args.kwargs['json']['body']
        assert '大盘复盘内容' in body

    def test_user_error_does_not_affect_others(self, monkeypatch, tmp_path):
        """一个用户发送失败不影响其他用户"""
        yaml = """
users:
  - name: 用户B
    device_key: key-b
    stocks: [600519]
  - name: 用户C
    device_key: key-c
    stocks: [300750]
"""
        path = tmp_path / 'push_config.yaml'
        path.write_text(yaml, encoding='utf-8')
        monkeypatch.setattr('stock_analysis.push_config.DEFAULT_CONFIG_PATH', path)
        monkeypatch.setenv('STOCK_LIST', '600519,300750')

        def fake_post(url, **kwargs):
            response = Mock()
            response.status_code = 200
            if 'key-b' in url:
                raise Exception('Bark 网络错误')
            response.json.return_value = {'code': 200}
            return response

        result_maotai = make_full_result()
        result_catl = make_full_result(code='300750', name='宁德时代')

        with patch('stock_analysis.notification.requests.post', side_effect=fake_post):
            status = send_user_notifications([result_maotai, result_catl], title='测试')

        assert status['用户B'] is False
        assert status['用户C'] is True

    def test_no_config_falls_back_empty(self, monkeypatch):
        """无 push_config 配置时返回空（走旧逻辑）"""
        monkeypatch.setenv('STOCK_LIST', '600519')
        with patch('stock_analysis.push_config.DEFAULT_CONFIG_PATH') as mock_path:
            mock_path.exists.return_value = False
            from stock_analysis.notification import send_user_notifications
            status = send_user_notifications([make_result()])
        assert status == {}


# ========== 整股截断测试（不拆分单只股票信息） ==========

class TestWholeStockTruncation:

    def test_long_content_drops_whole_stocks(self, monkeypatch):
        """内容超长时整股丢弃（从评分最低开始），不切碎单只股票"""
        from stock_analysis import notification as notif

        # 构造 8 只内容较大的股票（每只约 600+ 字符）
        results = []
        for i in range(8):
            r = make_full_result()
            r.code = f'60000{i}'
            r.name = f'测试股票{i}'
            r.sentiment_score = 90 - i * 5
            r.dashboard['battle_plan']['sniper_points'] = {
                'ideal_buy': f'理想买入点：1{i}.00元附近（MA5附近，乖离率0.4{i}%）',
                'stop_loss': f'止损位：1{i}.50元（跌破MA20支撑）',
                'take_profit': f'目标位：2{i}.00元（整数关口+前高）',
            }
            results.append(r)

        content = notif._generate_bark_content(results)

        # 总长不超限
        assert len(content) <= notif.MAX_BARK_LENGTH + 20
        # 有省略标注
        assert '已省略' in content
        # 出现过的股票代码必须完整（整只出现，不半截）
        appeared_codes = []
        for r in results:
            if f'({r.code})' in content:
                appeared_codes.append(r.code)
        assert appeared_codes, "至少应有一只完整股票"
        # 高分股票优先保留
        assert '600000' in appeared_codes  # 评分 90 最高，必须保留
        # 低分股票被省略
        assert '600007' not in content  # 评分最低的整只被丢弃

    def test_normal_content_no_truncation(self, monkeypatch):
        """内容未超限时不省略任何股票"""
        from stock_analysis import notification as notif
        content = notif._generate_bark_content([make_full_result(), make_result()])
        assert '已省略' not in content
        assert '贵州茅台' in content
