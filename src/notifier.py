import logging
import requests
import json
import pandas as pd

logger = logging.getLogger(__name__)

class FeishuNotifier:
    """
    飞书群机器人 Webhook 通知器。
    从 config.json 传入 webhook_url，发送格式化的纯文本消息。
    """
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        
        if not self.webhook_url:
            logger.warning("未配置 feishu_webhook 参数，将只打印结构化报警信息而不实际发送飞书网络通知。")

    def send_signal_alert(self, symbol: str, trigger_time: str, reason: str, current_price: float):
        """
        发送量化报警信号到飞书。
        参数：
            symbol: 股票代码
            trigger_time: 触发时间
            reason: 触发原因
            current_price: 触发时的当前股价
        """
        # 注意：必须以用户指定的关键词 【股票提醒】 开头
        text = (
            f"【股票提醒】\n"
            f"标的代码: {symbol}\n"
            f"触发时间: {trigger_time}\n"
            f"触发原因: {reason}\n"
            f"当前股价: {current_price:.2f} 元"
        )
        
        if not self.webhook_url:
            # 在没有配置 webhook 的情况下，降级为本地格式化输出
            logger.info(f"【模拟推送 - 飞书】\n{text}")
            return
            
        headers = {"Content-Type": "application/json"}
        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }
        
        try:
            response = requests.post(self.webhook_url, headers=headers, data=json.dumps(payload), timeout=5)
            response.raise_for_status()
            logger.info(f"成功发送飞书报警至 Webhook: {symbol} [{reason}]")
        except Exception as e:
            logger.error(f"飞书报警发送失败: {e}", exc_info=True)

    def send_broadcast(self, mode: str, results: list, alerts: list, market_overview: str = "", accuracy_data: dict = None):
        """
        发送每日播报及整合的风险信号预警。
        参数：
            mode: 运行模式 (start/mid/end)
            results: 单只股票最新指标信息列表
            alerts: 触发的风险预警列表
            market_overview: 每日市场概览 (板块等)
            accuracy_data: 准确率看板数据
        """
        if not results and not alerts:
            text = "⚠️【股票提醒】今日数据抓取全线失败，请检查网络或 IP 状态。"
            
            if not self.webhook_url:
                logger.info(f"【模拟推送 - 飞书播报】\n{text}")
                return
                
            headers = {"Content-Type": "application/json"}
            payload = {"msg_type": "text", "content": {"text": text}}
            try:
                requests.post(self.webhook_url, headers=headers, data=json.dumps(payload), timeout=5)
                logger.info("成功发送幸存者播报")
            except Exception as e:
                logger.error(f"飞书幸存者播报发送失败: {e}")
            return

        if mode == 'start':
            text = "🌅【股票提醒】早安！A 股已开市。目前监控已就位，祝今日红盘！\n"
        elif mode == 'mid':
             text = "🌞【股票提醒】午盘总结\n"
             if market_overview:
                 text += f"\n📊【每日市场概览】\n{market_overview}\n"
             text += "\n📈【标的深度分析】\n"
             for res in results:
                 pct = res.get('pct_change', 0)
                 text += f" - {res['symbol']}: 半日涨跌幅 {pct:+.2%}\n"
        elif mode == 'end':
            text = "🌙【A股量化监控 - 每日复盘】\n"
            
            if market_overview:
                text += f"\n📊【每日市场概览】\n{market_overview}\n"
                
            text += "\n📈【标的深度分析】\n"
            for res in results:
                close = res.get('close', 0)
                tech = res.get('tech_score', 0)
                sent = res.get('sentiment_score', 0)
                chip = res.get('chip_score', 0)
                state = res.get('market_state', 'Neutral')
                
                text += f" - {res['symbol']}: 收盘价 {close:.2f}\n"
                text += f"   ➤ 技术面:{tech} | 舆情:{sent} | 筹码:{chip} => 状态: {state}\n"
                
            text += "\n🎯【量化操作计划】\n"
            for res in results:
                sugg = res.get('suggestion', '建议观望')
                text += f" - {res['symbol']}: {sugg}\n"
                
            text += "\n🏆【准确率看板】\n"
            if accuracy_data:
                for days, stats in accuracy_data.items():
                    rate = stats.get('rate', 0)
                    total = stats.get('total', 0)
                    text += f" - 过去 {days} 天: 胜率 {rate:.2%} (共{total}次判定)\n"
            else:
                text += " - 暂无足够数据评估\n"
        else:
            return

        if alerts:
            text += "\n⚠️【风控预警信号】⚠️\n"
            for alt in alerts:
                symbol = alt.get('symbol', '未知')
                reason_parts = []
                if alt.get('sell_warning'):
                    reason_parts.append("卖出信号（RSI>70且跌破20日均线）")
                if alt.get('unusual_drop_warning'):
                    reason_parts.append("异常跌幅（单日下跌超5%）")
                reason = "；".join(reason_parts) if reason_parts else "风控预警触发"
                current_price = alt.get('close', 0.0)
                text += f" - {symbol}: {reason} (当前价: {current_price:.2f})\n"

        text += "\n💡 温馨提示：本分析仅供参考，不构成任何投资建议，股市有风险，入市需谨慎。"

        if not self.webhook_url:
            logger.info(f"【模拟推送 - 飞书播报】\n{text}")
            return
            
        headers = {"Content-Type": "application/json"}
        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }
        
        try:
            response = requests.post(self.webhook_url, headers=headers, data=json.dumps(payload), timeout=5)
            response.raise_for_status()
            logger.info(f"成功发送飞书播报 (模式: {mode})")
        except Exception as e:
            logger.error(f"飞书播报发送失败: {e}", exc_info=True)
