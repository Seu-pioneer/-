import os
import gc
import time
import logging
from typing import List, Optional
from datetime import datetime

import akshare as ak
import pandas as pd

# 1. 确保日志与数据输出目录存在 (防报错防御机制)
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

# 2. 配置标准日志记录器 (Logger)
# 同步输出至终端与本地 log 文件，便于后期排查网络或接口阻断问题
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/fetcher_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8')
    ]
)

def fetch_fund_nav_optimized(fund_codes: List[str], start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    批量获取开放式基金历史净值，采用块处理与强制垃圾回收 (Garbage Collection, GC) 机制。
    
    Args:
        fund_codes (List[str]): 基金代码列表
        start_date (str): 起始日期，格式 'YYYY-MM-DD' 或 'YYYYMMDD'
        end_date (str): 结束日期，格式 'YYYY-MM-DD' 或 'YYYYMMDD'
        
    Returns:
        Optional[pd.DataFrame]: 拼接后的纵向面板数据。如果全量抓取失败则返回 None。
    """
    all_data_chunks: List[pd.DataFrame] = []
    
    for idx, code in enumerate(fund_codes):
        logging.info(f"正在抓取基金 {code} 的数据 ({idx+1}/{len(fund_codes)})...")
        try:
            # 依据现行 akshare 标准，调用东方财富 (EastMoney) 接口获取单位净值走势
            df_temp: pd.DataFrame = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            
            # 字段重命名与时间轴对齐
            df_temp = df_temp.rename(columns={
                "净值日期": "date", 
                "单位净值": "unit_nav", 
                "日增长率": "daily_return"
            })
            df_temp['date'] = pd.to_datetime(df_temp['date'])
            df_temp['fund_code'] = code
            
            # 时间切片与空值清洗
            mask = (df_temp['date'] >= pd.to_datetime(start_date)) & (df_temp['date'] <= pd.to_datetime(end_date))
            df_cleaned: pd.DataFrame = df_temp.loc[mask].copy()
            df_cleaned.dropna(subset=['unit_nav'], inplace=True)
            
            # 数据类型降级 (Downcasting) 优化：将 float64 强制降维至 float32，直接削减 50% 的浮点内存占用
            df_cleaned['unit_nav'] = df_cleaned['unit_nav'].astype('float32')
            df_cleaned['daily_return'] = df_cleaned['daily_return'].astype('float32')
            
            all_data_chunks.append(df_cleaned)
            
        except Exception as e:
            logging.error(f"抓取基金 {code} 异常，可能为接口限流或标的不存在: {e}")
            
        finally:
            # 显式解除局部变量的内存引用
            if 'df_temp' in locals():
                del df_temp
            if 'df_cleaned' in locals():
                del df_cleaned
            
            # 强制触发 Python 底层的垃圾回收器，防止 16GB 内存溢出 (OOM)
            gc.collect()
            
            # 设置爬虫阻滞 (Sleep)，避免高频请求触发 IP 封禁
            time.sleep(1.2) 

    if not all_data_chunks:
        logging.warning("全量抓取失败，返回空集。")
        return None
        
    # 将独立的数据块合并为全局 DataFrame
    final_df: pd.DataFrame = pd.concat(all_data_chunks, ignore_index=True)
    return final_df

if __name__ == "__main__":
    # 测试标的：易方达蓝筹精选(005827)、中欧医疗健康(003096)、华泰柏瑞沪深300ETF联接(460300)
    target_funds: List[str] = ["005827", "003096", "460300"] 
    today_str: str = datetime.now().strftime("%Y%m%d")
    
    result_df = fetch_fund_nav_optimized(
        fund_codes=target_funds, 
        start_date="20220101", 
        end_date=today_str
    )
    
    if result_df is not None:
        # [逻辑闭环检查] 强制使用 Parquet 列式存储。禁止使用 CSV。
        output_path: str = os.path.join("data", f"fund_nav_pool_{today_str}.parquet")
        result_df.to_parquet(output_path, engine='pyarrow', index=False)
        logging.info(f"管道运行完毕。结果已序列化至 {output_path}，当前数据集总行数: {len(result_df)}。")