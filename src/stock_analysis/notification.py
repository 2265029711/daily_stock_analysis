# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 通知层
===================================

职责：
1. 汇总分析结果生成日报
2. 支持 Markdown 格式输出
3. 多渠道独立推送（企业微信 / Bark），互不影响
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests

from stock_analysis.config import get_config
from stock_analysis.analyzer import AnalysisResult

logger = logging.getLogger(__name__)


class BarkNotifier:
    """
    Bark 推送服务（iOS 通知）

    支持官方服务器（https://api.day.app）或自建服务器
    通过简单 HTTP POST 推送通知
    """

    def __init__(
        self,
        device_key: Optional[str] = None,
        server_url: Optional[str] = None,
        group: Optional[str] = None,
    ):
        """
        初始化 Bark 推送服务

        Args:
            device_key: Bark 设备 Key（可选，默认从配置读取）
            server_url: Bark 服务器地址（可选，默认 https://api.day.app）
            group: 通知分组（可选，默认 股票分析）
        """
        config = get_config()
        self._device_key = device_key or config.bark_device_key
        self._server_url = (server_url or config.bark_server_url).rstrip('/')
        self._group = group or config.bark_group

        if not self._device_key:
            logger.warning("Bark 设备 Key 未配置，将不发送 Bark 推送")

    def is_available(self) -> bool:
        """检查 Bark 服务是否可用"""
        return bool(self._device_key)

    def send_to_bark(self, title: str, content: str, group: Optional[str] = None) -> bool:
        """
        推送消息到 Bark

        官方服务器地址: https://api.day.app/{device_key}
        自建服务器地址: {server_url}/{device_key}

        Args:
            title: 通知标题
            content: 通知内容
            group: 通知分组（可选，默认使用配置的分组）

        Returns:
            是否发送成功
        """
        if not self.is_available():
            logger.warning("Bark 设备 Key 未配置，跳过 Bark 推送")
            return False

        url = f"{self._server_url}/{self._device_key}"

        payload = {
            "title": title,
            "body": content,
            "group": group or self._group,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200:
                    logger.info("Bark 消息发送成功")
                    return True
                else:
                    logger.error(f"Bark 返回错误: {result}")
                    return False
            else:
                logger.error(f"Bark 请求失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Bark 发送失败: {e}")
            return False


class NotificationService:
    """
    通知服务
    
    职责：
    1. 生成 Markdown 格式的分析日报
    2. 推送消息到企业微信机器人
    3. 支持本地保存日报
    """
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        初始化通知服务
        
        Args:
            webhook_url: 企业微信 Webhook URL（可选，默认从配置读取）
        """
        self._webhook_url = webhook_url or get_config().wechat_webhook_url
        
        if not self._webhook_url:
            logger.warning("企业微信 Webhook URL 未配置，将不发送推送通知")
    
    def is_available(self) -> bool:
        """检查通知服务是否可用"""
        return bool(self._webhook_url)
    
    def generate_daily_report(
        self, 
        results: List[AnalysisResult],
        report_date: Optional[str] = None
    ) -> str:
        """
        生成 Markdown 格式的日报（详细版）
        
        Args:
            results: 分析结果列表
            report_date: 报告日期（默认今天）
            
        Returns:
            Markdown 格式的日报内容
        """
        if report_date is None:
            report_date = datetime.now().strftime('%Y-%m-%d')
        
        # 标题
        report_lines = [
            f"# 📅 {report_date} A股自选股智能分析报告",
            "",
            f"> 共分析 **{len(results)}** 只股票 | 报告生成时间：{datetime.now().strftime('%H:%M:%S')}",
            "",
            "---",
            "",
        ]
        
        # 按评分排序（高分在前）
        sorted_results = sorted(
            results, 
            key=lambda x: x.sentiment_score, 
            reverse=True
        )
        
        # 统计信息
        buy_count = sum(1 for r in results if r.operation_advice in ['买入', '加仓', '强烈买入'])
        sell_count = sum(1 for r in results if r.operation_advice in ['卖出', '减仓', '强烈卖出'])
        hold_count = sum(1 for r in results if r.operation_advice in ['持有', '观望'])
        avg_score = sum(r.sentiment_score for r in results) / len(results) if results else 0
        
        report_lines.extend([
            "## 📊 操作建议汇总",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 🟢 建议买入/加仓 | **{buy_count}** 只 |",
            f"| 🟡 建议持有/观望 | **{hold_count}** 只 |",
            f"| 🔴 建议减仓/卖出 | **{sell_count}** 只 |",
            f"| 📈 平均看多评分 | **{avg_score:.1f}** 分 |",
            "",
            "---",
            "",
            "## 📈 个股详细分析",
            "",
        ])
        
        # 逐个股票的详细分析
        for result in sorted_results:
            emoji = result.get_emoji()
            confidence_stars = result.get_confidence_stars() if hasattr(result, 'get_confidence_stars') else '⭐⭐'
            
            report_lines.extend([
                f"### {emoji} {result.name} ({result.code})",
                "",
                f"**操作建议：{result.operation_advice}** | **综合评分：{result.sentiment_score}分** | **趋势预测：{result.trend_prediction}** | **置信度：{confidence_stars}**",
                "",
            ])
            
            # 核心看点
            if hasattr(result, 'key_points') and result.key_points:
                report_lines.extend([
                    f"**🎯 核心看点**：{result.key_points}",
                    "",
                ])
            
            # 买入/卖出理由
            if hasattr(result, 'buy_reason') and result.buy_reason:
                report_lines.extend([
                    f"**💡 操作理由**：{result.buy_reason}",
                    "",
                ])
            
            # 走势分析
            if hasattr(result, 'trend_analysis') and result.trend_analysis:
                report_lines.extend([
                    "#### 📉 走势分析",
                    f"{result.trend_analysis}",
                    "",
                ])
            
            # 短期/中期展望
            outlook_lines = []
            if hasattr(result, 'short_term_outlook') and result.short_term_outlook:
                outlook_lines.append(f"- **短期（1-3日）**：{result.short_term_outlook}")
            if hasattr(result, 'medium_term_outlook') and result.medium_term_outlook:
                outlook_lines.append(f"- **中期（1-2周）**：{result.medium_term_outlook}")
            if outlook_lines:
                report_lines.extend([
                    "#### 🔮 市场展望",
                    *outlook_lines,
                    "",
                ])
            
            # 技术面分析
            tech_lines = []
            if result.technical_analysis:
                tech_lines.append(f"**综合**：{result.technical_analysis}")
            if hasattr(result, 'ma_analysis') and result.ma_analysis:
                tech_lines.append(f"**均线**：{result.ma_analysis}")
            if hasattr(result, 'volume_analysis') and result.volume_analysis:
                tech_lines.append(f"**量能**：{result.volume_analysis}")
            if hasattr(result, 'pattern_analysis') and result.pattern_analysis:
                tech_lines.append(f"**形态**：{result.pattern_analysis}")
            if tech_lines:
                report_lines.extend([
                    "#### 📊 技术面分析",
                    *tech_lines,
                    "",
                ])
            
            # 基本面分析
            fund_lines = []
            if hasattr(result, 'fundamental_analysis') and result.fundamental_analysis:
                fund_lines.append(result.fundamental_analysis)
            if hasattr(result, 'sector_position') and result.sector_position:
                fund_lines.append(f"**板块地位**：{result.sector_position}")
            if hasattr(result, 'company_highlights') and result.company_highlights:
                fund_lines.append(f"**公司亮点**：{result.company_highlights}")
            if fund_lines:
                report_lines.extend([
                    "#### 🏢 基本面分析",
                    *fund_lines,
                    "",
                ])
            
            # 消息面/情绪面
            news_lines = []
            if result.news_summary:
                news_lines.append(f"**新闻摘要**：{result.news_summary}")
            if hasattr(result, 'market_sentiment') and result.market_sentiment:
                news_lines.append(f"**市场情绪**：{result.market_sentiment}")
            if hasattr(result, 'hot_topics') and result.hot_topics:
                news_lines.append(f"**相关热点**：{result.hot_topics}")
            if news_lines:
                report_lines.extend([
                    "#### 📰 消息面/情绪面",
                    *news_lines,
                    "",
                ])
            
            # 综合分析
            if result.analysis_summary:
                report_lines.extend([
                    "#### 📝 综合分析",
                    result.analysis_summary,
                    "",
                ])
            
            # 风险提示
            if hasattr(result, 'risk_warning') and result.risk_warning:
                report_lines.extend([
                    f"⚠️ **风险提示**：{result.risk_warning}",
                    "",
                ])
            
            # 数据来源说明
            if hasattr(result, 'search_performed') and result.search_performed:
                report_lines.append(f"*🔍 已执行联网搜索*")
            if hasattr(result, 'data_sources') and result.data_sources:
                report_lines.append(f"*📋 数据来源：{result.data_sources}*")
            
            # 错误信息（如果有）
            if not result.success and result.error_message:
                report_lines.extend([
                    "",
                    f"❌ **分析异常**：{result.error_message[:100]}",
                ])
            
            report_lines.extend([
                "",
                "---",
                "",
            ])
        
        # 底部信息（去除免责声明）
        report_lines.extend([
            "",
            f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])
        
        return "\n".join(report_lines)
    
    def _get_signal_level(self, result: AnalysisResult) -> tuple:
        """
        根据操作建议获取信号等级和颜色
        
        Returns:
            (信号文字, emoji, 颜色标记)
        """
        advice = result.operation_advice
        score = result.sentiment_score
        
        if advice in ['强烈买入'] or score >= 80:
            return ('强烈买入', '💚', '强买')
        elif advice in ['买入', '加仓'] or score >= 65:
            return ('买入', '🟢', '买入')
        elif advice in ['持有'] or 55 <= score < 65:
            return ('持有', '🟡', '持有')
        elif advice in ['观望'] or 45 <= score < 55:
            return ('观望', '⚪', '观望')
        elif advice in ['减仓'] or 35 <= score < 45:
            return ('减仓', '🟠', '减仓')
        elif advice in ['卖出', '强烈卖出'] or score < 35:
            return ('卖出', '🔴', '卖出')
        else:
            return ('观望', '⚪', '观望')
    
    def generate_dashboard_report(
        self, 
        results: List[AnalysisResult],
        report_date: Optional[str] = None
    ) -> str:
        """
        生成决策仪表盘格式的日报（详细版）
        
        格式：市场概览 + 重要信息 + 核心结论 + 数据透视 + 作战计划
        
        Args:
            results: 分析结果列表
            report_date: 报告日期（默认今天）
            
        Returns:
            Markdown 格式的决策仪表盘日报
        """
        if report_date is None:
            report_date = datetime.now().strftime('%Y-%m-%d')
        
        # 按评分排序（高分在前）
        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)
        
        # 统计信息
        buy_count = sum(1 for r in results if r.operation_advice in ['买入', '加仓', '强烈买入'])
        sell_count = sum(1 for r in results if r.operation_advice in ['卖出', '减仓', '强烈卖出'])
        hold_count = sum(1 for r in results if r.operation_advice in ['持有', '观望'])
        
        report_lines = [
            f"# 🎯 {report_date} 决策仪表盘",
            "",
            f"> 共分析 **{len(results)}** 只股票 | 🟢买入:{buy_count} 🟡观望:{hold_count} 🔴卖出:{sell_count}",
            "",
            "---",
            "",
        ]
        
        # 逐个股票的决策仪表盘
        for result in sorted_results:
            signal_text, signal_emoji, signal_tag = self._get_signal_level(result)
            dashboard = result.dashboard if hasattr(result, 'dashboard') and result.dashboard else {}
            
            # 股票名称（优先使用 dashboard 或 result 中的名称）
            stock_name = result.name if result.name and not result.name.startswith('股票') else f'股票{result.code}'
            
            report_lines.extend([
                f"## {signal_emoji} {stock_name} ({result.code})",
                "",
            ])
            
            # ========== 舆情与基本面概览（放在最前面）==========
            intel = dashboard.get('intelligence', {}) if dashboard else {}
            if intel:
                report_lines.extend([
                    "### 📰 重要信息速览",
                    "",
                ])
                
                # 舆情情绪总结
                if intel.get('sentiment_summary'):
                    report_lines.append(f"**💭 舆情情绪**: {intel['sentiment_summary']}")
                
                # 业绩预期
                if intel.get('earnings_outlook'):
                    report_lines.append(f"**📊 业绩预期**: {intel['earnings_outlook']}")
                
                # 风险警报（醒目显示）
                risk_alerts = intel.get('risk_alerts', [])
                if risk_alerts:
                    report_lines.append("")
                    report_lines.append("**🚨 风险警报**:")
                    for alert in risk_alerts:
                        report_lines.append(f"- {alert}")
                
                # 利好催化
                catalysts = intel.get('positive_catalysts', [])
                if catalysts:
                    report_lines.append("")
                    report_lines.append("**✨ 利好催化**:")
                    for cat in catalysts:
                        report_lines.append(f"- {cat}")
                
                # 最新消息
                if intel.get('latest_news'):
                    report_lines.append("")
                    report_lines.append(f"**📢 最新动态**: {intel['latest_news']}")
                
                report_lines.append("")
            
            # ========== 核心结论 ==========
            core = dashboard.get('core_conclusion', {}) if dashboard else {}
            one_sentence = core.get('one_sentence', result.analysis_summary)
            time_sense = core.get('time_sensitivity', '本周内')
            pos_advice = core.get('position_advice', {})
            
            report_lines.extend([
                "### 📌 核心结论",
                "",
                f"**{signal_emoji} {signal_text}** | {result.trend_prediction}",
                "",
                f"> **一句话决策**: {one_sentence}",
                "",
                f"⏰ **时效性**: {time_sense}",
                "",
            ])
            
            # 持仓分类建议
            if pos_advice:
                report_lines.extend([
                    "| 持仓情况 | 操作建议 |",
                    "|---------|---------|",
                    f"| 🆕 **空仓者** | {pos_advice.get('no_position', result.operation_advice)} |",
                    f"| 💼 **持仓者** | {pos_advice.get('has_position', '继续持有')} |",
                    "",
                ])
            
            # ========== 数据透视 ==========
            data_persp = dashboard.get('data_perspective', {}) if dashboard else {}
            if data_persp:
                trend_data = data_persp.get('trend_status', {})
                price_data = data_persp.get('price_position', {})
                vol_data = data_persp.get('volume_analysis', {})
                chip_data = data_persp.get('chip_structure', {})
                
                report_lines.extend([
                    "### 📊 数据透视",
                    "",
                ])
                
                # 趋势状态
                if trend_data:
                    is_bullish = "✅ 是" if trend_data.get('is_bullish', False) else "❌ 否"
                    report_lines.extend([
                        f"**均线排列**: {trend_data.get('ma_alignment', 'N/A')} | 多头排列: {is_bullish} | 趋势强度: {trend_data.get('trend_score', 'N/A')}/100",
                        "",
                    ])
                
                # 价格位置
                if price_data:
                    bias_status = price_data.get('bias_status', 'N/A')
                    bias_emoji = "✅" if bias_status == "安全" else ("⚠️" if bias_status == "警戒" else "🚨")
                    report_lines.extend([
                        "| 价格指标 | 数值 |",
                        "|---------|------|",
                        f"| 当前价 | {price_data.get('current_price', 'N/A')} |",
                        f"| MA5 | {price_data.get('ma5', 'N/A')} |",
                        f"| MA10 | {price_data.get('ma10', 'N/A')} |",
                        f"| MA20 | {price_data.get('ma20', 'N/A')} |",
                        f"| 乖离率(MA5) | {price_data.get('bias_ma5', 'N/A')}% {bias_emoji}{bias_status} |",
                        f"| 支撑位 | {price_data.get('support_level', 'N/A')} |",
                        f"| 压力位 | {price_data.get('resistance_level', 'N/A')} |",
                        "",
                    ])
                
                # 量能分析
                if vol_data:
                    report_lines.extend([
                        f"**量能**: 量比 {vol_data.get('volume_ratio', 'N/A')} ({vol_data.get('volume_status', '')}) | 换手率 {vol_data.get('turnover_rate', 'N/A')}%",
                        f"💡 *{vol_data.get('volume_meaning', '')}*",
                        "",
                    ])
                
                # 筹码结构
                if chip_data:
                    chip_health = chip_data.get('chip_health', 'N/A')
                    chip_emoji = "✅" if chip_health == "健康" else ("⚠️" if chip_health == "一般" else "🚨")
                    report_lines.extend([
                        f"**筹码**: 获利比例 {chip_data.get('profit_ratio', 'N/A')} | 平均成本 {chip_data.get('avg_cost', 'N/A')} | 集中度 {chip_data.get('concentration', 'N/A')} {chip_emoji}{chip_health}",
                        "",
                    ])
            
            # 舆情情报已移至顶部显示
            
            # ========== 作战计划 ==========
            battle = dashboard.get('battle_plan', {}) if dashboard else {}
            if battle:
                report_lines.extend([
                    "### 🎯 作战计划",
                    "",
                ])
                
                # 狙击点位
                sniper = battle.get('sniper_points', {})
                if sniper:
                    report_lines.extend([
                        "**📍 狙击点位**",
                        "",
                        "| 点位类型 | 价格 |",
                        "|---------|------|",
                        f"| 🎯 理想买入点 | {sniper.get('ideal_buy', 'N/A')} |",
                        f"| 🔵 次优买入点 | {sniper.get('secondary_buy', 'N/A')} |",
                        f"| 🛑 止损位 | {sniper.get('stop_loss', 'N/A')} |",
                        f"| 🎊 目标位 | {sniper.get('take_profit', 'N/A')} |",
                        "",
                    ])
                
                # 仓位策略
                position = battle.get('position_strategy', {})
                if position:
                    report_lines.extend([
                        f"**💰 仓位建议**: {position.get('suggested_position', 'N/A')}",
                        f"- 建仓策略: {position.get('entry_plan', 'N/A')}",
                        f"- 风控策略: {position.get('risk_control', 'N/A')}",
                        "",
                    ])
                
                # 检查清单
                checklist = battle.get('action_checklist', [])
                if checklist:
                    report_lines.extend([
                        "**✅ 检查清单**",
                        "",
                    ])
                    for item in checklist:
                        report_lines.append(f"- {item}")
                    report_lines.append("")
            
            # 如果没有 dashboard，显示传统格式
            if not dashboard:
                # 操作理由
                if result.buy_reason:
                    report_lines.extend([
                        f"**💡 操作理由**: {result.buy_reason}",
                        "",
                    ])
                
                # 风险提示
                if result.risk_warning:
                    report_lines.extend([
                        f"**⚠️ 风险提示**: {result.risk_warning}",
                        "",
                    ])
                
                # 技术面分析
                if result.ma_analysis or result.volume_analysis:
                    report_lines.extend([
                        "### 📊 技术面",
                        "",
                    ])
                    if result.ma_analysis:
                        report_lines.append(f"**均线**: {result.ma_analysis}")
                    if result.volume_analysis:
                        report_lines.append(f"**量能**: {result.volume_analysis}")
                    report_lines.append("")
                
                # 消息面
                if result.news_summary:
                    report_lines.extend([
                        "### 📰 消息面",
                        f"{result.news_summary}",
                        "",
                    ])
            
            report_lines.extend([
                "---",
                "",
            ])
        
        # 底部（去除免责声明）
        report_lines.extend([
            "",
            f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        ])
        
        return "\n".join(report_lines)
    
    def generate_wechat_dashboard(self, results: List[AnalysisResult]) -> str:
        """
        生成企业微信决策仪表盘精简版（控制在4000字符内）
        
        只保留核心结论和狙击点位
        
        Args:
            results: 分析结果列表
            
        Returns:
            精简版决策仪表盘
        """
        report_date = datetime.now().strftime('%Y-%m-%d')
        
        # 按评分排序
        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)
        
        # 统计
        buy_count = sum(1 for r in results if r.operation_advice in ['买入', '加仓', '强烈买入'])
        sell_count = sum(1 for r in results if r.operation_advice in ['卖出', '减仓', '强烈卖出'])
        hold_count = sum(1 for r in results if r.operation_advice in ['持有', '观望'])
        
        lines = [
            f"## 🎯 {report_date} 决策仪表盘",
            "",
            f"> {len(results)}只股票 | 🟢买入:{buy_count} 🟡观望:{hold_count} 🔴卖出:{sell_count}",
            "",
        ]
        
        for result in sorted_results:
            signal_text, signal_emoji, _ = self._get_signal_level(result)
            dashboard = result.dashboard if hasattr(result, 'dashboard') and result.dashboard else {}
            core = dashboard.get('core_conclusion', {}) if dashboard else {}
            battle = dashboard.get('battle_plan', {}) if dashboard else {}
            intel = dashboard.get('intelligence', {}) if dashboard else {}
            
            # 股票名称
            stock_name = result.name if result.name and not result.name.startswith('股票') else f'股票{result.code}'
            
            # 标题行：信号等级 + 股票名称
            lines.append(f"### {signal_emoji} **{signal_text}** | {stock_name}({result.code})")
            lines.append("")
            
            # 核心决策（一句话）
            one_sentence = core.get('one_sentence', result.analysis_summary) if core else result.analysis_summary
            if one_sentence:
                lines.append(f"📌 **{one_sentence[:80]}**")
                lines.append("")
            
            # 重要信息区（舆情+基本面）
            info_lines = []
            
            # 业绩预期
            if intel.get('earnings_outlook'):
                outlook = intel['earnings_outlook'][:60]
                info_lines.append(f"📊 业绩: {outlook}")
            
            # 舆情情绪
            if intel.get('sentiment_summary'):
                sentiment = intel['sentiment_summary'][:50]
                info_lines.append(f"💭 舆情: {sentiment}")
            
            if info_lines:
                lines.extend(info_lines)
                lines.append("")
            
            # 风险警报（最重要，醒目显示）
            risks = intel.get('risk_alerts', []) if intel else []
            if risks:
                lines.append("🚨 **风险**:")
                for risk in risks[:2]:  # 最多显示2条
                    risk_text = risk[:50] + "..." if len(risk) > 50 else risk
                    lines.append(f"   • {risk_text}")
                lines.append("")
            
            # 利好催化
            catalysts = intel.get('positive_catalysts', []) if intel else []
            if catalysts:
                lines.append("✨ **利好**:")
                for cat in catalysts[:2]:  # 最多显示2条
                    cat_text = cat[:50] + "..." if len(cat) > 50 else cat
                    lines.append(f"   • {cat_text}")
                lines.append("")
            
            # 狙击点位
            sniper = battle.get('sniper_points', {}) if battle else {}
            if sniper:
                ideal_buy = sniper.get('ideal_buy', '')
                stop_loss = sniper.get('stop_loss', '')
                take_profit = sniper.get('take_profit', '')
                
                points = []
                if ideal_buy:
                    points.append(f"🎯买点:{ideal_buy[:15]}")
                if stop_loss:
                    points.append(f"🛑止损:{stop_loss[:15]}")
                if take_profit:
                    points.append(f"🎊目标:{take_profit[:15]}")
                
                if points:
                    lines.append(" | ".join(points))
                    lines.append("")
            
            # 持仓建议
            pos_advice = core.get('position_advice', {}) if core else {}
            if pos_advice:
                no_pos = pos_advice.get('no_position', '')
                has_pos = pos_advice.get('has_position', '')
                if no_pos:
                    lines.append(f"🆕 空仓者: {no_pos[:50]}")
                if has_pos:
                    lines.append(f"💼 持仓者: {has_pos[:50]}")
                lines.append("")
            
            # 检查清单简化版
            checklist = battle.get('action_checklist', []) if battle else []
            if checklist:
                # 只显示不通过的项目
                failed_checks = [c for c in checklist if c.startswith('❌') or c.startswith('⚠️')]
                if failed_checks:
                    lines.append("**检查未通过项**:")
                    for check in failed_checks[:3]:
                        lines.append(f"   {check[:40]}")
                    lines.append("")
            
            lines.append("---")
            lines.append("")
        
        # 底部
        lines.append(f"*生成时间: {datetime.now().strftime('%H:%M')}*")
        
        content = "\n".join(lines)
        
        # 检查长度
        if len(content) > 3800:
            logger.warning(f"仪表盘超长({len(content)}字符)，截断")
            content = content[:3800] + "\n...(已截断)"
        
        return content
    
    def generate_wechat_summary(self, results: List[AnalysisResult]) -> str:
        """
        生成企业微信精简版日报（控制在4000字符内）
        
        Args:
            results: 分析结果列表
            
        Returns:
            精简版 Markdown 内容
        """
        report_date = datetime.now().strftime('%Y-%m-%d')
        
        # 按评分排序
        sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)
        
        # 统计
        buy_count = sum(1 for r in results if r.operation_advice in ['买入', '加仓', '强烈买入'])
        sell_count = sum(1 for r in results if r.operation_advice in ['卖出', '减仓', '强烈卖出'])
        hold_count = sum(1 for r in results if r.operation_advice in ['持有', '观望'])
        avg_score = sum(r.sentiment_score for r in results) / len(results) if results else 0
        
        lines = [
            f"## 📅 {report_date} A股分析报告",
            "",
            f"> 共 **{len(results)}** 只 | 🟢买入:{buy_count} 🟡持有:{hold_count} 🔴卖出:{sell_count} | 均分:{avg_score:.0f}",
            "",
        ]
        
        # 每只股票精简信息（控制长度）
        for result in sorted_results:
            emoji = result.get_emoji()
            
            # 核心信息行
            lines.append(f"### {emoji} {result.name}({result.code})")
            lines.append(f"**{result.operation_advice}** | 评分:{result.sentiment_score} | {result.trend_prediction}")
            
            # 操作理由（截断）
            if hasattr(result, 'buy_reason') and result.buy_reason:
                reason = result.buy_reason[:80] + "..." if len(result.buy_reason) > 80 else result.buy_reason
                lines.append(f"💡 {reason}")
            
            # 核心看点
            if hasattr(result, 'key_points') and result.key_points:
                points = result.key_points[:60] + "..." if len(result.key_points) > 60 else result.key_points
                lines.append(f"🎯 {points}")
            
            # 风险提示（截断）
            if hasattr(result, 'risk_warning') and result.risk_warning:
                risk = result.risk_warning[:50] + "..." if len(result.risk_warning) > 50 else result.risk_warning
                lines.append(f"⚠️ {risk}")
            
            lines.append("")
        
        # 底部
        lines.extend([
            "---",
            "*AI生成，仅供参考，不构成投资建议*",
            f"*详细报告见 reports/report_{report_date.replace('-', '')}.md*"
        ])
        
        content = "\n".join(lines)
        
        # 最终检查长度
        if len(content) > 3800:
            logger.warning(f"精简报告仍超长({len(content)}字符)，进行截断")
            content = content[:3800] + "\n\n...(内容过长已截断)"
        
        return content
    
    def send_to_wechat(self, content: str) -> bool:
        """
        推送消息到企业微信机器人
        
        企业微信 Webhook 消息格式：
        {
            "msgtype": "markdown",
            "markdown": {
                "content": "Markdown 内容"
            }
        }
        
        注意：企业微信 Markdown 限制 4096 字符
        
        Args:
            content: Markdown 格式的消息内容
            
        Returns:
            是否发送成功
        """
        if not self.is_available():
            logger.warning("企业微信 Webhook 未配置，跳过推送")
            return False
        
        # 检查长度
        if len(content) > 4000:
            logger.warning(f"消息内容超长({len(content)}字符)，将截断至4000字符")
            content = content[:3950] + "\n\n...(内容过长已截断，详见完整报告)"
        
        try:
            return self._send_single_message(content)
        except Exception as e:
            logger.error(f"发送企业微信消息失败: {e}")
            return False
    
    def _send_single_message(self, content: str) -> bool:
        """发送单条消息"""
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        
        response = requests.post(
            self._webhook_url,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("企业微信消息发送成功")
                return True
            else:
                logger.error(f"企业微信返回错误: {result}")
                return False
        else:
            logger.error(f"企业微信请求失败: {response.status_code}")
            return False
    
    def _send_chunked_messages(self, content: str, max_length: int) -> bool:
        """
        分段发送长消息
        
        按段落（---）分割，确保每段不超过最大长度
        """
        # 按分隔线分割
        sections = content.split("\n---\n")
        
        current_chunk = []
        current_length = 0
        all_success = True
        chunk_index = 1
        
        for section in sections:
            section_with_divider = section + "\n---\n"
            section_length = len(section_with_divider)
            
            if current_length + section_length > max_length:
                # 发送当前块
                if current_chunk:
                    chunk_content = "\n---\n".join(current_chunk)
                    logger.info(f"发送消息块 {chunk_index}...")
                    if not self._send_single_message(chunk_content):
                        all_success = False
                    chunk_index += 1
                
                # 重置
                current_chunk = [section]
                current_length = section_length
            else:
                current_chunk.append(section)
                current_length += section_length
        
        # 发送最后一块
        if current_chunk:
            chunk_content = "\n---\n".join(current_chunk)
            logger.info(f"发送消息块 {chunk_index}（最后）...")
            if not self._send_single_message(chunk_content):
                all_success = False
        
        return all_success
    
    def save_report_to_file(
        self, 
        content: str, 
        filename: Optional[str] = None
    ) -> str:
        """
        保存日报到本地文件
        
        Args:
            content: 日报内容
            filename: 文件名（可选，默认按日期生成）
            
        Returns:
            保存的文件路径
        """
        from pathlib import Path
        
        if filename is None:
            date_str = datetime.now().strftime('%Y%m%d')
            filename = f"report_{date_str}.md"
        
        # 确保 reports 目录存在（项目根目录，src/stock_analysis/ 上两级）
        reports_dir = Path(__file__).resolve().parents[2] / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"日报已保存到: {filepath}")
        return str(filepath)


class NotificationBuilder:
    """
    通知消息构建器
    
    提供便捷的消息构建方法
    """
    
    @staticmethod
    def build_simple_alert(
        title: str,
        content: str,
        alert_type: str = "info"
    ) -> str:
        """
        构建简单的提醒消息
        
        Args:
            title: 标题
            content: 内容
            alert_type: 类型（info, warning, error, success）
        """
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
        }
        emoji = emoji_map.get(alert_type, "📢")
        
        return f"{emoji} **{title}**\n\n{content}"
    
    @staticmethod
    def build_stock_summary(results: List[AnalysisResult]) -> str:
        """
        构建股票摘要（简短版）
        
        适用于快速通知
        """
        lines = ["📊 **今日自选股摘要**", ""]
        
        for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):
            emoji = r.get_emoji()
            lines.append(f"{emoji} {r.name}({r.code}): {r.operation_advice} | 评分 {r.sentiment_score}")
        
        return "\n".join(lines)


# 便捷函数
def get_notification_service() -> NotificationService:
    """获取通知服务实例"""
    return NotificationService()


def send_text_notifications(content: str, title: str = "") -> Dict[str, bool]:
    """
    多渠道统一分发文本通知（企业微信 / Bark），互不影响

    Args:
        content: 文本内容（如大盘复盘报告）
        title: 通知标题（Bark 使用）

    Returns:
        {渠道名: 是否发送成功} 字典
    """
    config = get_config()
    status: Dict[str, bool] = {}

    # 渠道 1: 企业微信
    if config.wechat_webhook_url:
        try:
            service = NotificationService()
            status['wechat'] = service.send_to_wechat(content)
        except Exception as e:
            logger.error(f"企业微信推送异常（不影响其他渠道）: {e}")
            status['wechat'] = False
    else:
        logger.info("企业微信未配置，跳过该渠道")

    # 渠道 2: Bark
    if config.bark_device_key:
        try:
            bark = BarkNotifier()
            status['bark'] = bark.send_to_bark(title or "📊 通知", content)
        except Exception as e:
            logger.error(f"Bark 推送异常（不影响其他渠道）: {e}")
            status['bark'] = False
    else:
        logger.info("Bark 未配置，跳过该渠道")

    if not status:
        logger.warning("未配置任何通知渠道（企业微信 / Bark），跳过推送")

    return status


def send_notifications(results: List[AnalysisResult], title: str = "") -> Dict[str, bool]:
    """
    多渠道统一分发通知（企业微信 / Bark）

    渠道独立原则：
    - 各渠道根据自身配置独立判断是否启用
    - 任一渠道失败/未配置，不影响其他渠道
    - 只启用已配置的渠道，无硬编码依赖

    Args:
        results: 分析结果列表
        title: 通知标题（Bark 使用）

    Returns:
        {渠道名: 是否发送成功} 字典
    """
    config = get_config()
    status: Dict[str, bool] = {}

    # 渠道 1: 企业微信
    if config.wechat_webhook_url:
        try:
            service = NotificationService()
            content = service.generate_wechat_dashboard(results)
            status['wechat'] = service.send_to_wechat(content)
        except Exception as e:
            logger.error(f"企业微信推送异常（不影响其他渠道）: {e}")
            status['wechat'] = False
    else:
        logger.info("企业微信未配置，跳过该渠道")

    # 渠道 2: Bark
    if config.bark_device_key:
        try:
            bark = BarkNotifier()
            content = _generate_bark_content(results)
            status['bark'] = bark.send_to_bark(title or "🎯 每日决策仪表盘", content)
        except Exception as e:
            logger.error(f"Bark 推送异常（不影响其他渠道）: {e}")
            status['bark'] = False
    else:
        logger.info("Bark 未配置，跳过该渠道")

    if not status:
        logger.warning("未配置任何通知渠道（企业微信 / Bark），跳过推送")

    return status


def send_user_notifications(
    results: List[AnalysisResult],
    market_report: Optional[str] = None,
    title: str = "",
) -> Dict[str, bool]:
    """
    多用户分发生成通知（push_config.yaml）

    每个用户独立推送，互不影响：
    - stocks 用户：按配置过滤个股结果，生成标准模板内容推送
    - push_market 用户：推送大盘复盘报告

    Args:
        results: 全部股票分析结果
        market_report: 大盘复盘报告文本（可选）
        title: 通知标题前缀

    Returns:
        {用户名称: 是否发送成功} 字典
    """
    from stock_analysis.push_config import get_push_config

    config = get_config()
    push_config = get_push_config()

    if not push_config.is_configured:
        logger.warning("未配置有效的多用户推送（push_config.yaml 缺失或无有效用户）")
        return {}

    report_date = datetime.now().strftime('%Y-%m-%d')
    status: Dict[str, bool] = {}

    for user in push_config.users:
        try:
            bark = BarkNotifier(
                device_key=user.device_key,
                server_url=user.server_url,
                group=user.group,
            )
            ok = True

            # 个股推送
            if user.wants_stocks:
                user_stocks = push_config.get_user_stocks(user, config.stock_list)
                user_results = [r for r in results if r.code in user_stocks]
                if user_results:
                    content = _generate_bark_content(user_results)
                    title_text = title or f"🎯 {report_date} 决策仪表盘"
                    if not bark.send_to_bark(title_text, content):
                        ok = False
                        logger.warning(f"[用户 {user.name}] 个股推送失败")
                else:
                    logger.warning(f"[用户 {user.name}] 未找到匹配的分析结果: {user_stocks}")

            # 大盘复盘推送
            if user.push_market and market_report:
                market_title = f"🎯 {report_date} 大盘复盘"
                if not bark.send_to_bark(market_title, market_report):
                    ok = False
                    logger.warning(f"[用户 {user.name}] 大盘复盘推送失败")

            status[user.name] = ok
            if ok:
                logger.info(f"[用户 {user.name}] 推送成功")
        except Exception as e:
            logger.error(f"[用户 {user.name}] 推送异常（不影响其他用户）: {e}")
            status[user.name] = False

    return status


def _build_stock_block(r: AnalysisResult) -> List[str]:
    """
    构建单只股票的推送块（标准推送模板）

    模板结构（固定顺序）：
    1. 🟢 名称(代码) | 操作建议 | 评分 | 趋势
    2. 📊 实时行情（价格/量比/换手/PE/PB/市值）
    3. 📈 技术面（均线/乖离率/趋势分/信号）
    4. 📰 情报（新闻/风险/利好）
    5. 💡 结论（LLM 一句话）
    6. 📌 理由（操作依据）
    7. 📍 狙击点位（买/损/标，完整描述）
    8. ⚠️ 提示（风险提示）

    注意：单只股票的所有信息必须完整输出在同一块内，
    不允许多只股票的信息拆分到不同推送。
    """
    emoji = r.get_emoji()
    dashboard = r.dashboard or {}
    core = dashboard.get('core_conclusion', {}) if dashboard else {}
    battle = dashboard.get('battle_plan', {}) if dashboard else {}
    intel = dashboard.get('intelligence', {}) if dashboard else {}

    lines = [
        f"{emoji} {r.name}({r.code}) | {r.operation_advice} | 评分{r.sentiment_score} | {r.trend_prediction}",
        "",
    ]

    # ===== 1. 实时行情（原始数据，非 LLM 转述） =====
    rt = r.realtime_data or {}
    if rt:
        price = rt.get('price')
        change_pct = rt.get('change_pct')
        parts = []
        if price:
            pct_str = f"({change_pct:+.2f}%)" if isinstance(change_pct, (int, float)) else ""
            parts.append(f"现价 {price}{pct_str}")
        if rt.get('volume_ratio') is not None:
            parts.append(f"量比 {rt.get('volume_ratio')}")
        if rt.get('turnover_rate') is not None:
            parts.append(f"换手 {rt.get('turnover_rate')}%")
        if rt.get('pe_ratio'):
            parts.append(f"PE {rt.get('pe_ratio')}")
        if rt.get('pb_ratio'):
            parts.append(f"PB {rt.get('pb_ratio')}")
        mv = _fmt_amount(rt.get('total_mv'))
        if mv != "N/A":
            parts.append(f"市值 {mv}")
        if parts:
            lines.append(f"📊 实时行情: {' | '.join(parts)}")

    # ===== 2. 技术面（均线/乖离率/趋势评分） =====
    tr = r.trend_data or {}
    if tr:
        tech_parts = []
        if tr.get('ma_alignment'):
            tech_parts.append(f"均线 {tr.get('ma_alignment')}")
        if isinstance(tr.get('bias_ma5'), (int, float)):
            bias = tr.get('bias_ma5')
            mark = "🚨" if bias > 5 else ("⚠️" if bias > 2 else "✅")
            tech_parts.append(f"乖离 {bias:+.2f}%{mark}")
        if tr.get('signal_score') is not None:
            tech_parts.append(f"趋势分 {tr.get('signal_score')}")
        if tr.get('buy_signal'):
            tech_parts.append(f"信号 {tr.get('buy_signal')}")
        if tech_parts:
            lines.append(f"📈 技术面: {' | '.join(tech_parts)}")

    # ===== 3. 情报摘要（新闻/风险/利好，完整输出） =====
    if intel.get('latest_news'):
        lines.append(f"📰 {intel.get('latest_news')}")
    risk_alerts = intel.get('risk_alerts', []) or []
    if risk_alerts:
        lines.append(f"🚨 风险: {risk_alerts[0]}")
    catalysts = intel.get('positive_catalysts', []) or []
    if catalysts:
        lines.append(f"✨ 利好: {catalysts[0]}")

    # ===== 4. LLM 结论（带理由） =====
    one_sentence = core.get('one_sentence', r.analysis_summary)
    if one_sentence:
        lines.append(f"💡 结论: {one_sentence}")

    reason = r.buy_reason
    if not reason:
        pos_advice = core.get('position_advice', {}) or {}
        reason = pos_advice.get('no_position') or pos_advice.get('has_position') or ""
    if reason:
        lines.append(f"📌 理由: {reason}")

    # ===== 5. 狙击点位（完整描述，不截断） =====
    sniper = battle.get('sniper_points', {}) or {}
    points = []
    for label, key in (("买", "ideal_buy"), ("损", "stop_loss"), ("标", "take_profit")):
        text = (sniper.get(key) or "").strip()
        if text:
            points.append(f"{label}: {text}")
    if points:
        lines.append(f"📍 {'；'.join(points)}")

    if r.risk_warning:
        lines.append(f"⚠️ 提示: {r.risk_warning}")

    lines.append("---")
    lines.append("")

    return lines


def _fmt_amount(value) -> str:
    """格式化市值（元 -> 亿）"""
    try:
        v = float(value)
        if v >= 1e8:
            return f"{v / 1e8:.0f}亿"
        if v > 0:
            return f"{v:.0f}万"
        return "N/A"
    except (TypeError, ValueError):
        return "N/A"


# Bark 服务器内容长度上限（约 3000 字符，留 200 余量）
MAX_BARK_LENGTH = 2800


def _generate_bark_content(results: List[AnalysisResult]) -> str:
    """
    生成 Bark 推送内容（标准模板 + 整股截断）

    布局原则：数据先行，LLM 结论收尾

    截断策略（保证不拆股）：
    - 按标准模板生成每只股票的完整 block
    - 依次拼接，超长时从评分最低的股票开始整只丢弃
    - 绝不在一只股票内部切分，也不跨推送拆分
    """
    report_date = datetime.now().strftime('%Y-%m-%d')

    # 统计
    buy_count = sum(1 for r in results if r.operation_advice in ['买入', '加仓', '强烈买入'])
    sell_count = sum(1 for r in results if r.operation_advice in ['卖出', '减仓', '强烈卖出'])
    hold_count = sum(1 for r in results if r.operation_advice in ['持有', '观望'])

    header = [
        f"🎯 {report_date} 决策仪表盘",
        f"{len(results)}只 | 🟢买入:{buy_count} 🟡观望:{hold_count} 🔴卖出:{sell_count}",
        "",
    ]

    # 生成所有股票块（按评分从高到低）
    sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)
    blocks = {r.code: _build_stock_block(r) for r in sorted_results}

    # 依次拼接完整块，超长时整块丢弃（从评分最低的开始）
    lines = list(header)
    omitted = 0
    for r in sorted_results:
        block = blocks[r.code]
        block_text = "\n".join(block)
        # 预测拼接后的长度（含尾部信息行）
        tail = [f"*生成时间: {datetime.now().strftime('%H:%M')} | AI生成仅供参考*"]
        if omitted:
            tail.append(f"*(已省略 {omitted} 只股票)*")
        preview = "\n".join(lines + block + tail)
        if len(preview) > MAX_BARK_LENGTH:
            omitted += 1
            continue
        lines.extend(block)

    if omitted:
        logger.warning(f"Bark 内容超长，已省略 {omitted} 只股票（整股截断）")

    lines.append(f"*生成时间: {datetime.now().strftime('%H:%M')} | AI生成仅供参考*")
    if omitted:
        lines.append(f"*(已省略 {omitted} 只股票)*")

    return "\n".join(lines)


def send_daily_report(results: List[AnalysisResult]) -> bool:
    """
    发送每日报告的快捷方式
    
    自动生成报告并推送到企业微信
    """
    service = get_notification_service()
    
    # 生成报告
    report = service.generate_daily_report(results)
    
    # 保存到本地
    service.save_report_to_file(report)
    
    # 推送到企业微信
    return service.send_to_wechat(report)


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    # 模拟分析结果
    test_results = [
        AnalysisResult(
            code='600519',
            name='贵州茅台',
            sentiment_score=75,
            trend_prediction='看多',
            analysis_summary='技术面强势，消息面利好',
            operation_advice='买入',
            technical_analysis='放量突破 MA20，MACD 金叉',
            news_summary='公司发布分红公告，业绩超预期',
        ),
        AnalysisResult(
            code='000001',
            name='平安银行',
            sentiment_score=45,
            trend_prediction='震荡',
            analysis_summary='横盘整理，等待方向',
            operation_advice='持有',
            technical_analysis='均线粘合，成交量萎缩',
            news_summary='近期无重大消息',
        ),
        AnalysisResult(
            code='300750',
            name='宁德时代',
            sentiment_score=35,
            trend_prediction='看空',
            analysis_summary='技术面走弱，注意风险',
            operation_advice='卖出',
            technical_analysis='跌破 MA10 支撑，量能不足',
            news_summary='行业竞争加剧，毛利率承压',
        ),
    ]
    
    service = NotificationService()
    
    # 生成日报
    print("=== 生成日报测试 ===")
    report = service.generate_daily_report(test_results)
    print(report)
    
    # 保存到文件
    print("\n=== 保存日报 ===")
    filepath = service.save_report_to_file(report)
    print(f"保存成功: {filepath}")
    
    # 推送测试（仅当配置了 Webhook 时）
    if service.is_available():
        print("\n=== 推送测试 ===")
        success = service.send_to_wechat(report)
        print(f"推送结果: {'成功' if success else '失败'}")
    else:
        print("\n企业微信 Webhook 未配置，跳过推送测试")
