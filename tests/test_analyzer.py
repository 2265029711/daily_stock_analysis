# -*- coding: utf-8 -*-
"""AI 分析器（OpenAI 兼容）单元测试"""
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_analysis.analyzer import OpenAIAnalyzer
from stock_analysis.config import Config, get_config


@pytest.fixture(autouse=True)
def reset_config(monkeypatch):
    """重置配置单例，并用空值屏蔽 .env 中的真实配置"""
    for env in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL',
                'BARK_DEVICE_KEY', 'BARK_SERVER_URL', 'BARK_GROUP',
                'WECHAT_WEBHOOK_URL', 'STOCK_LIST'):
        monkeypatch.setenv(env, '')
    # 数值型配置设为文档默认值（空串会导致 float/int 解析报错）
    monkeypatch.setenv('OPENAI_REQUEST_DELAY', '2.0')
    monkeypatch.setenv('OPENAI_MAX_RETRIES', '5')
    monkeypatch.setenv('OPENAI_RETRY_DELAY', '5.0')
    Config.reset_instance()
    yield
    Config.reset_instance()


def make_analyzer(monkeypatch, client=None, api_key='sk-test-key-123456'):
    """构造带 mock 客户端的分析器"""
    monkeypatch.setenv('OPENAI_API_KEY', api_key)
    monkeypatch.setenv('OPENAI_MODEL', 'test-model')
    analyzer = OpenAIAnalyzer()
    client = client or Mock()
    analyzer._openai_client = client
    analyzer._current_model_name = 'test-model'
    # 关闭重试延时，加速测试
    get_config().openai_retry_delay = 0
    get_config().openai_request_delay = 0
    return analyzer


def make_completion(content: str):
    """构造 OpenAI 格式的完成响应"""
    message = Mock()
    message.content = content
    choice = Mock()
    choice.message = message
    response = Mock()
    response.choices = [choice]
    return response


VALID_JSON = json.dumps({
    "sentiment_score": 75,
    "trend_prediction": "看多",
    "operation_advice": "买入",
    "confidence_level": "高",
    "dashboard": {
        "core_conclusion": {
            "one_sentence": "回踩MA5可介入",
            "signal_type": "🟢买入信号",
            "time_sensitivity": "今日内",
            "position_advice": {
                "no_position": "空仓者可在回踩时建仓",
                "has_position": "持仓者可继续持有"
            }
        },
        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "1800元",
                "stop_loss": "1750元",
                "take_profit": "1900元"
            },
            "action_checklist": ["✅ 多头排列", "✅ 乖离率<5%"]
        },
        "intelligence": {
            "risk_alerts": ["风险：大额解禁"],
            "positive_catalysts": ["利好：业绩预增"]
        }
    },
    "analysis_summary": "技术面强势，可介入",
    "key_points": "多头排列,量能配合",
    "risk_warning": "注意解禁风险",
    "buy_reason": "缩量回踩MA5",
    "trend_analysis": "上升趋势",
    "short_term_outlook": "短期看涨",
    "medium_term_outlook": "中期震荡上行",
    "technical_analysis": "技术指标良好",
    "ma_analysis": "多头排列",
    "volume_analysis": "缩量回调",
    "pattern_analysis": "W底",
    "fundamental_analysis": "基本面稳健",
    "sector_position": "行业龙头",
    "company_highlights": "业绩增长",
    "news_summary": "近期无重大利空",
    "market_sentiment": "乐观",
    "hot_topics": "新能源",
    "search_performed": True,
    "data_sources": "技术面+新闻"
}, ensure_ascii=False)


def test_is_available_with_client(monkeypatch):
    """有客户端时 is_available 返回 True"""
    analyzer = make_analyzer(monkeypatch)
    assert analyzer.is_available() is True


def test_is_available_without_client(monkeypatch):
    """无有效 Key 时 is_available 返回 False"""
    monkeypatch.setenv('OPENAI_API_KEY', '')
    Config.reset_instance()
    analyzer = OpenAIAnalyzer()
    assert analyzer.is_available() is False


def test_placeholder_key_invalid(monkeypatch):
    """占位符 Key（your_ 开头）被视为无效"""
    monkeypatch.setenv('OPENAI_API_KEY', 'your_openai_key_here')
    Config.reset_instance()
    analyzer = OpenAIAnalyzer()
    assert analyzer._openai_client is None
    assert analyzer.is_available() is False


def test_init_without_model(monkeypatch):
    """有 Key 但未配置 OPENAI_MODEL 时模型名为 None（不预设默认）"""
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key-123456')
    monkeypatch.setenv('OPENAI_MODEL', '')
    Config.reset_instance()
    analyzer = OpenAIAnalyzer()
    assert analyzer.is_available() is True
    assert analyzer._current_model_name is None


def test_call_openai_api_success(monkeypatch):
    """正常调用返回内容"""
    analyzer = make_analyzer(monkeypatch)
    analyzer._openai_client.chat.completions.create.return_value = make_completion('分析结果')
    result = analyzer._call_openai_api('prompt', {'temperature': 0.7, 'max_output_tokens': 8192})
    assert result == '分析结果'
    analyzer._openai_client.chat.completions.create.assert_called_once()


def test_call_openai_api_retry_on_empty(monkeypatch):
    """空响应触发重试，最终成功"""
    analyzer = make_analyzer(monkeypatch)
    get_config().openai_max_retries = 3
    analyzer._openai_client.chat.completions.create.side_effect = [
        make_completion(''),  # 第一次空响应
        make_completion('第二次成功'),
    ]
    result = analyzer._call_openai_api('prompt', {'temperature': 0.7})
    assert result == '第二次成功'
    assert analyzer._openai_client.chat.completions.create.call_count == 2


def test_call_openai_api_rate_limit_retry(monkeypatch):
    """429 限流触发指数退避重试"""
    analyzer = make_analyzer(monkeypatch)
    get_config().openai_max_retries = 3
    error = Exception('429 Too Many Requests')
    analyzer._openai_client.chat.completions.create.side_effect = [
        error, error, make_completion('限流后成功'),
    ]
    result = analyzer._call_openai_api('prompt', {'temperature': 0.7})
    assert result == '限流后成功'
    assert analyzer._openai_client.chat.completions.create.call_count == 3


def test_call_openai_api_fail_after_max_retries(monkeypatch):
    """达到最大重试次数后抛出异常"""
    analyzer = make_analyzer(monkeypatch)
    get_config().openai_max_retries = 2
    analyzer._openai_client.chat.completions.create.side_effect = Exception('500 Server Error')
    with pytest.raises(Exception, match='500'):
        analyzer._call_openai_api('prompt', {'temperature': 0.7})
    assert analyzer._openai_client.chat.completions.create.call_count == 2


def test_analyze_success(monkeypatch):
    """analyze() 解析完整 JSON 返回 AnalysisResult"""
    analyzer = make_analyzer(monkeypatch)
    analyzer._openai_client.chat.completions.create.return_value = make_completion(VALID_JSON)
    context = {
        'code': '600519',
        'date': '2026-01-09',
        'today': {'close': 1820.0, 'ma5': 1810.0, 'ma10': 1800.0, 'ma20': 1790.0},
    }
    result = analyzer.analyze(context)
    assert result.success is True
    assert result.code == '600519'
    assert result.sentiment_score == 75
    assert result.trend_prediction == '看多'
    assert result.operation_advice == '买入'
    assert result.dashboard['core_conclusion']['one_sentence'] == '回踩MA5可介入'
    assert result.get_sniper_points()['ideal_buy'] == '1800元'
    assert result.get_risk_alerts() == ['风险：大额解禁']


def test_analyze_json_in_code_fence(monkeypatch):
    """响应带 ```json 代码块时仍能正确解析"""
    analyzer = make_analyzer(monkeypatch)
    wrapped = f"```json\n{VALID_JSON}\n```"
    analyzer._openai_client.chat.completions.create.return_value = make_completion(wrapped)
    context = {'code': '600519', 'today': {'close': 1820.0}}
    result = analyzer.analyze(context)
    assert result.success is True
    assert result.sentiment_score == 75


def test_analyze_trailing_comma_fix(monkeypatch):
    """响应含尾随逗号时被修复后解析"""
    analyzer = make_analyzer(monkeypatch)
    broken = VALID_JSON.replace('"key_points": "多头排列,量能配合",', '"key_points": "多头排列,量能配合",,')
    broken = broken.replace('"analysis_summary": "技术面强势，可介入",', '"analysis_summary": "技术面强势，可介入",,')
    analyzer._openai_client.chat.completions.create.return_value = make_completion(broken)
    context = {'code': '600519', 'today': {'close': 1820.0}}
    result = analyzer.analyze(context)
    assert result.success is True


def test_analyze_text_fallback(monkeypatch):
    """响应非 JSON 时降级为文本解析"""
    analyzer = make_analyzer(monkeypatch)
    analyzer._openai_client.chat.completions.create.return_value = make_completion('该股看多，建议买入')
    context = {'code': '600519', 'today': {'close': 1820.0}}
    result = analyzer.analyze(context)
    assert result.success is True
    assert '看多' in result.analysis_summary or result.sentiment_score == 65


def test_analyze_truncated_json_repaired(monkeypatch):
    """响应被截断（LLM 输出超限）时修复为可解析 JSON"""
    analyzer = make_analyzer(monkeypatch)
    # 真实场景：LLM 输出在 ideal_buy 值中途被截断（后续内容 + 外层闭合括号全部丢失）
    cut_marker = '"ideal_buy": "'
    idx = VALID_JSON.find(cut_marker)
    truncated = VALID_JSON[:idx] + '"ideal_buy": "理想买入点：18'
    analyzer._openai_client.chat.completions.create.return_value = make_completion(truncated)
    context = {'code': '600519', 'today': {'close': 1820.0}}
    result = analyzer.analyze(context)
    # 截断修复后仍能解析出核心字段（缺失字段使用默认值）
    assert result.success is True
    assert result.sentiment_score == 75
    assert result.trend_prediction == '看多'
    assert result.operation_advice == '买入'
    assert result.dashboard is not None


def test_text_fallback_no_raw_json_dump(monkeypatch):
    """JSON 解析彻底失败时，摘要不倾倒原始 JSON（避免推送乱码）"""
    analyzer = make_analyzer(monkeypatch)
    # 完全损坏的 JSON（开头 { 结尾无闭合）
    broken = '{"sentiment_score": 45, "trend_prediction": "震荡", "operation_advice": "观望", "analysis_summary": "被截断'
    analyzer._openai_client.chat.completions.create.return_value = make_completion(broken)
    context = {'code': '600519', 'today': {'close': 1820.0}}
    result = analyzer.analyze(context)
    assert result.success is True
    assert '{' not in result.analysis_summary
    assert '格式异常' in result.analysis_summary


def test_analyze_without_key(monkeypatch):
    """无 API Key 时 analyze() 返回默认失败结果"""
    monkeypatch.setenv('OPENAI_API_KEY', '')
    Config.reset_instance()
    analyzer = OpenAIAnalyzer()
    context = {'code': '600519', 'today': {'close': 1820.0}}
    result = analyzer.analyze(context)
    assert result.success is False
    assert 'OpenAI API Key' in result.error_message
