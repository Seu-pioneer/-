import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from google import genai

# 1. 加载环境变量与代理配置
load_dotenv()

proxy = os.getenv("PROXY_URL")
if proxy:
    # 强制路由请求至本地代理，防止 API 调用超时
    os.environ["http_proxy"] = proxy
    os.environ["https_proxy"] = proxy

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("未检测到 API Key，请检查 .env 文件！")

# 初始化 Gemini 客户端
client = genai.Client(api_key=api_key)

def calculate_metrics(df: pd.DataFrame) -> str:
    """计算量化指标，并格式化为大语言模型的上下文"""
    summary_lines = []
    
    # 按基金代码分组计算
    for code, group in df.groupby("fund_code"):
        group = group.sort_values("date")
        if len(group) == 0:
            continue
        
        # 计算基础财务指标
        start_nav = group["unit_nav"].iloc[0]
        end_nav = group["unit_nav"].iloc[-1]
        total_return = (end_nav - start_nav) / start_nav * 100
        
        # 计算最大回撤 (Max Drawdown)
        cumulative_returns = group["unit_nav"] / group["unit_nav"].iloc[0]
        rolling_max = cumulative_returns.cummax()
        drawdowns = (cumulative_returns - rolling_max) / rolling_max
        max_drawdown = drawdowns.min() * 100
        
        summary_lines.append(
            f"- 标的 {code}: 区间收益率 {total_return:.2f}%, 最大回撤 {max_drawdown:.2f}%"
        )
        
    return "\n".join(summary_lines)

def generate_report():
    today_str = datetime.now().strftime("%Y%m%d")
    data_path = os.path.join("data", f"fund_nav_pool_{today_str}.parquet")
    
    if not os.path.exists(data_path):
        print(f"错误: 找不到今日的数据文件 {data_path}。请先运行 fetcher.py。")
        return
        
    print("1. 正在加载 Parquet 数据引擎...")
    df = pd.read_parquet(data_path)
    
    print("2. 正在进行量化指标运算...")
    context_data = calculate_metrics(df)
    
    print("3. 正在组装 Prompt 并请求大模型...")
    prompt = f"""
    你是一位专业的量化基金分析师。请基于以下我用 Python 算出的基金回测核心数据，写一份简短的《每日基金量化筛查与估值研报》。
    
    【数据上下文】
    {context_data}
    
    【输出要求】
    1. 必须使用 Markdown 格式。
    2. 包含“量化数据概览”、“异动点评”、“风险提示”三个核心模块。
    3. 语气要客观、专业、有深度，适合作为高质量的付费订阅内容输出。
    """
    
    # 调用 Gemini API (推荐使用速度较快的 flash 模型进行文本生成)
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    
    # 4. 研报持久化输出
    os.makedirs("docs", exist_ok=True)
    report_path = os.path.join("docs", f"Quant_Report_{today_str}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(response.text)
        
    print(f"\n✅ 商业化研报生成成功！已保存至: {report_path}")

if __name__ == "__main__":
    generate_report()