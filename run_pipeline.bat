@echo off
chcp 65001 >nul

:: 动态切换到工作区绝对路径
cd /d "%~dp0"

:: 注入网络代理穿透
set http_proxy=http://127.0.0.1:7890
set https_proxy=http://127.0.0.1:7890

echo [%date% %time%] Task Started >> logs\auto_run.log

:: 1. 优先运行估值测算雷达 (新增：强制输出决策日志)
D:\python\envs\quant_engine\python.exe src\valuation_radar.py >> logs\auto_run.log 2>&1

:: 2. 执行常规数据管道与 AI 研报生成
D:\python\envs\quant_engine\python.exe src\fetcher.py >> logs\auto_run.log 2>&1
D:\python\envs\quant_engine\python.exe src\analyzer.py >> logs\auto_run.log 2>&1

:: 3. 源码与数据全自动 Git 备份
git add .
git commit -m "auto-update: Daily Quant Report & Valuation" >> logs\auto_run.log 2>&1
git push origin master >> logs\auto_run.log 2>&1

:: 4. 触发静态网页编译与公网部署
D:\python\envs\quant_engine\Scripts\mkdocs.exe gh-deploy --force >> logs\auto_run.log 2>&1

echo [%date% %time%] Task Finished >> logs\auto_run.log
echo ---------------------------------------- >> logs\auto_run.log