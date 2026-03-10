"""
FMZ 回测引擎 POC 离线验证脚本 (Phase 1.5 修复版)

阶段一：POC 离线验证
- 在纯净、隔离的脚本中跑通 FMZ 底层逻辑
- 验证 FMZ 数据适配器与 PinbarStrategy 的集成
- 输出原生 C++ 回测结果到 tmp/fmz_sample_result.json

修复说明 (Phase 1.5):
- 修正回测循环模式：从"一次性获取 + for 循环"改为"while True + 实时滑动"
- 修正仓位计算：从"固定 0.1 BTC"改为"账户余额的 10%"
- 让 FMZ C++ 引擎时间轴正常推进，避免交易时间戳重叠
"""
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入 FMZ 模块（从项目根目录复制的 fmz.py）
from fmz import *

# 导入 Monitor 系统的组件
from core.entities import Bar, PinbarConfig, ScoringWeights
from domain.strategy.pinbar import PinbarStrategy
from infrastructure.backtest.fmz_adapter import fmz_records_to_bars

import json


def main():
    """
    FMZ 回测引擎 POC 验证主函数

    配置区间：2024 年 1 月 1 日 - 2024 年 2 月 1 日
    交易对：BTC_USDT
    周期：1 小时
    """

    # ==========================================
    # 1. FMZ 初始化配置字符串
    # ==========================================
    config_string = '''backtest
start: 2024-01-01 00:00:00
end: 2024-02-01 00:00:00
period: 1h
exchanges: [{"eid":"Binance","currency":"BTC_USDT","balance":100000,"stocks":0}]
'''

    print("=" * 60)
    print("FMZ 回测引擎 POC 验证 (Phase 1.5 修复版)")
    print("=" * 60)
    print(f"回测区间：2024-01-01 至 2024-02-01")
    print(f"交易对：BTC_USDT")
    print(f"周期：1 小时")
    print(f"初始资金：100,000 USDT")
    print(f"仓位策略：单笔 10% 余额")
    print("=" * 60)

    # ==========================================
    # 2. 启动 FMZ C++ 底层虚拟上下文
    # ==========================================
    print("\n[1/4] 初始化 FMZ C++ 引擎...")
    task = VCtx(config_string)
    print("      FMZ 引擎初始化成功")

    # ==========================================
    # 3. 实例化 Pinbar 策略大脑
    # ==========================================
    print("[2/4] 实例化 Pinbar 策略...")
    strategy = PinbarStrategy(ema_period=60, atr_period=14)
    pinbar_config = PinbarConfig()
    scoring_weights = ScoringWeights(w_shape=0.4, w_trend=0.3, w_vol=0.3)
    print("      PinbarStrategy(ema_period=60, atr_period=14) 就绪")

    # ==========================================
    # 4. 回测主循环 (while True 范式)
    # ==========================================
    print("[3/4] 开始回测主循环...")

    bar_count = 0
    signal_count = 0
    trade_count = 0
    last_print_bar = 0

    # 正确的 FMZ 回测主循环范式
    while True:
        # 4.1 从 FMZ 底层获取 K 线数据（每次调用时间轴向前推进）
        try:
            records = exchange.GetRecords()
        except EOFError:
            # FMZ C++ 引擎到达回测终点，抛出 EOFError
            print(f"      检测到 EOF，回测时间轴到达终点，退出循环")
            break

        # 4.2 无数据返回，说明回测时间轴到达终点
        if not records:
            print(f"      检测到回测终点，退出循环")
            break

        bar_count = len(records)

        # 进度日志（每 50 根 K 线打印一次）
        if bar_count - last_print_bar >= 50:
            print(f"      已处理 {bar_count} 根 K 线，发现 {signal_count} 个信号，执行 {trade_count} 笔交易")
            last_print_bar = bar_count

        # 4.3 数据转换：FMZ records -> Monitor Bars
        bars = fmz_records_to_bars(
            records=records,
            symbol="BTCUSDT",
            interval="1h",
            is_closed=True
        )

        # 4.4 历史数据不够 EMA 计算，跳过当前 tick
        min_bars_needed = 60  # EMA60 需要至少 60 根 K 线
        if len(bars) < min_bars_needed:
            continue

        # 4.5 分隔历史 K 线和当前 K 线
        history_bars = bars[:-1]   # 历史已闭合 K 线
        current_bar = bars[-1]     # 当前 K 线（最后一根）

        # 4.6 策略评估
        max_sl_dist = 0.035  # 最大止损距离 3.5%

        signal = strategy.evaluate(
            current_bar=current_bar,
            history_bars=history_bars,
            max_sl_dist=max_sl_dist,
            weights=scoring_weights,
            pinbar_config=pinbar_config
        )

        # 4.7 命中信号，执行模拟交易
        if signal:
            signal_count += 1

            # 动态仓位计算：使用账户余额的 10%
            account = exchange.GetAccount()
            balance = account['Balance']
            risk_amount = balance * 0.1  # 10% 余额
            trade_amount = risk_amount / current_bar.close

            # 执行交易
            if signal.direction == 'LONG':
                # 多单：调用 exchange.Buy()
                order_result = exchange.Buy(current_bar.close, trade_amount)
                if order_result:
                    trade_count += 1
                    if signal_count <= 10 or bar_count % 50 == 0:
                        print(f"      [{bar_count}] BUY {trade_amount:.4f} BTC @ {current_bar.close:.2f} "
                              f"(Score: {signal.score}, Balance: {balance:.2f})")
            else:
                # 空单：调用 exchange.Sell()
                order_result = exchange.Sell(current_bar.close, trade_amount)
                if order_result:
                    trade_count += 1
                    if signal_count <= 10 or bar_count % 50 == 0:
                        print(f"      [{bar_count}] SELL {trade_amount:.4f} BTC @ {current_bar.close:.2f} "
                              f"(Score: {signal.score}, Balance: {balance:.2f})")

    print(f"      回测循环结束：共处理 {bar_count} 根 K 线")

    # ==========================================
    # 5. 回收 FMZ 回测结果
    # ==========================================
    print("[4/4] 回收 FMZ C++ 回测结果...")
    result = task.Join()

    # FMZ Join() 返回的是 bytes，需要解码
    if isinstance(result, bytes):
        result = result.decode('utf-8')

    # ==========================================
    # 6. 输出结果到文件
    # ==========================================
    print("保存结果到 tmp/fmz_sample_result.json...")

    # 确保输出目录存在
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp')
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, 'fmz_sample_result.json')

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json.loads(result), f, indent=2, ensure_ascii=False)

    print(f"      结果已保存到：{output_path}")

    # ==========================================
    # 7. 摘要输出
    # ==========================================
    print("\n" + "=" * 60)
    print("回测完成摘要")
    print("=" * 60)

    # 解析结果
    try:
        result_dict = json.loads(result) if isinstance(result, str) else result

        # 提取关键统计信息
        if 'Snapshots' in result_dict:
            snapshots = result_dict['Snapshots']
            if snapshots:
                final_snapshot = snapshots[-1][1][0] if len(snapshots[-1][1]) > 0 else {}
                initial_snapshot = snapshots[0][1][0] if len(snapshots[0][1]) > 0 else {}

                print(f"初始资金：{initial_snapshot.get('Initial', 'N/A')} {initial_snapshot.get('MarginCurrency', 'USDT')}")
                print(f"最终权益：{final_snapshot.get('Balance', 'N/A')} {final_snapshot.get('MarginCurrency', 'USDT')}")
                print(f"总盈亏：{final_snapshot.get('PnL', 'N/A')} {final_snapshot.get('MarginCurrency', 'USDT')}")
                print(f"保证金使用率：{final_snapshot.get('Utilization', 'N/A') * 100:.2f}%")

        if 'ProfitLogs' in result_dict and result_dict['ProfitLogs']:
            profit_logs = result_dict['ProfitLogs']
            win_count = sum(1 for log in profit_logs if log.get('Profit', 0) > 0)
            loss_count = sum(1 for log in profit_logs if log.get('Profit', 0) < 0)
            total_trades = len(profit_logs)
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            gross_profit = sum(log.get('Profit', 0) for log in profit_logs if log.get('Profit', 0) > 0)
            gross_loss = abs(sum(log.get('Profit', 0) for log in profit_logs if log.get('Profit', 0) < 0))
            print(f"\n交易统计:")
            print(f"  平仓次数：{total_trades}")
            print(f"  盈利次数：{win_count}")
            print(f"  亏损次数：{loss_count}")
            print(f"  胜率：{win_rate:.2f}%")
            print(f"  总盈利：{gross_profit:.2f}")
            print(f"  总亏损：{gross_loss:.2f}")
        else:
            print("\nProfitLogs: 无平仓记录（持仓未平仓）")

        print(f"\n信号统计：共发现 {signal_count} 个交易信号")
        print(f"交易统计：共执行 {trade_count} 笔开仓")

        # 打印 RuntimeLogs 时间戳，验证时间轴是否正常步进
        if 'RuntimeLogs' in result_dict and result_dict['RuntimeLogs']:
            print(f"\nRuntimeLogs 时间戳验证（前 10 条）:")
            for i, log in enumerate(result_dict['RuntimeLogs'][:10]):
                if len(log) >= 2:
                    timestamp = log[1]
                    print(f"  [{i}] 时间戳：{timestamp}")

    except Exception as e:
        print(f"解析结果时出错：{e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)
    print("POC 验证完成！")
    print("=" * 60)

    return result


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
