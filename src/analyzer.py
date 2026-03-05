import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from google import genai

# 加载环境变量与网络代理
load_dotenv()
proxy = os.getenv("PROXY_URL")
if proxy:
    os.environ["http_proxy"] = proxy
    os.environ["https_proxy"] = proxy

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("未检测到 API Key，请检查 .env 文件！")

client = genai.Client(api_key=api_key)

def calculate_advanced_metrics(df: pd.DataFrame) -> str:
    """计算包含 MA20 与 MACD 的高级量化指标，并结构化输出为大模型上下文"""
    summary_lines = []
    
    for code, group in df.groupby("fund_code"):
        # 确保时间序列按升序排列
        group = group.sort_values("date").copy()
        if len(group) < 30:
            continue # 数据量不足无法计算长周期均线，跳过
            
        # 1. 基础指标计算
        start_nav = group["unit_nav"].iloc[0]
        latest_nav = group["unit_nav"].iloc[-1]
        total_return = (latest_nav - start_nav) / start_nav * 100
        
        cumulative_returns = group["unit_nav"] / group["unit_nav"].iloc[0]
        max_drawdown = ((cumulative_returns - cumulative_returns.cummax()) / cumulative_returns.cummax()).min() * 100
        
        # 2. MA20 均线系统计算
        group['MA20'] = group['unit_nav'].rolling(window=20).mean()
        latest_ma20 = group['MA20'].iloc[-1]
        # 判断当前净值是否站上 20 日均线
        trend_ma20 = "多头 (净值 > MA20)" if latest_nav > latest_ma20 else "空头 (净值 < MA20)"
        
        # 3. MACD 指标计算
        group['EMA12'] = group['unit_nav'].ewm(span=12, adjust=False).mean()
        group['EMA26'] = group['unit_nav'].ewm(span=26, adjust=False).mean()
        group['DIF'] = group['EMA12'] - group['EMA26']
        group['DEA'] = group['DIF'].ewm(span=9, adjust=False).mean()
        group['MACD'] = (group['DIF'] - group['DEA']) * 2
        
        latest_dif = group['DIF'].iloc[-1]
        latest_dea = group['DEA'].iloc[-1]
        latest_macd = group['MACD'].iloc[-1]
        prev_macd = group['MACD'].iloc[-2]
        
        # 提取 MACD 形态特征
        if latest_dif > latest_dea and group['DIF'].iloc[-2] <= group['DEA'].iloc[-2]:
            macd_signal = "出现金叉 (买入信号)"
        elif latest_dif < latest_dea and group['DIF'].iloc[-2] >= group['DEA'].iloc[-2]:
            macd_signal = "出现死叉 (卖出预警)"
        elif latest_macd > 0 and latest_macd > prev_macd:
            macd_signal = "红柱放大 (多头动能增强)"
        elif latest_macd < 0 and latest_macd < prev_macd:
            macd_signal = "绿柱放大 (空头动能增强)"
        else:
            macd_signal = "趋势震荡/动能衰减"

        summary_lines.append(
            f"【标的 {code}】\n"
            f"- 财务数据: 区间收益率 {total_return:.2f}%, 最大回撤 {max_drawdown:.2f}%\n"
            f"- MA20 趋势: {trend_ma20} (现价: {latest_nav:.4f}, MA20: {latest_ma20:.4f})\n"
            f"- MACD 信号: {macd_signal} (DIF: {latest_dif:.4f}, DEA: {latest_dea:.4f})\n"
        )
        
    return "\n".join(summary_lines)

def generate_report():
    today_str = datetime.now().strftime("%Y%m%d")
    data_path = os.path.join("data", f"fund_nav_pool_{today_str}.parquet")
    
    if not os.path.exists(data_path):
        print(f"错误: 找不到今日的数据文件 {data_path}。")
        return
        
    print("1. 正在加载 Parquet 数据引擎...")
    df = pd.read_parquet(data_path)
    
    print("2. 正在进行 MA20 与 MACD 因子测算...")
    context_data = calculate_advanced_metrics(df)
    
    print("3. 正在组装深度 Prompt 并请求大模型...")
    prompt = f"""
    你是一位顶级的量化策略分析师。请基于以下我用 Python 计算出的基金技术面测算数据，撰写今日的《量化基准测算与趋势研报》。
    
    【技术面测算上下文】
    {context_data}
    
    【输出要求】
    1. 必须使用 Markdown 格式。
    2. 包含以下三个模块：
       - **市场动能概览**: 总结当前给定的基金池整体处于多头还是空头周期。
       - **技术形态点评**: 基于提供的 MA20 和 MACD 信号，逐一点评各个基金的短期操作逻辑（例如：金叉是否确立、跌破均线是否需要减仓）。
       - **风控纪律提示**: 基于最大回撤数据给出防守建议。
    3. 风格必须极度专业、客观、不带任何煽动性情绪，杜绝空话套话，直击交易逻辑。
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    
    os.makedirs("docs", exist_ok=True)
    report_path = os.path.join("docs", f"Quant_Report_{today_str}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(response.text)
        
    print(f"\n量化测算研报生成成功！已保存至: {report_path}")

if __name__ == "__main__":
    generate_report()