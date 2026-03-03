@echo off
chcp 65001 >nul

:: 切换到脚本绝对路径
cd /d "%~dp0"

set http_proxy=http://127.0.0.1:7890
set https_proxy=http://127.0.0.1:7890

:: 使用纯英文避免 Windows 追加写入时出现乱码
echo [%date% %time%] Task Started >> logs\auto_run.log

D:\python\envs\quant_engine\python.exe src\fetcher.py >> logs\auto_run.log 2>&1
D:\python\envs\quant_engine\python.exe src\analyzer.py >> logs\auto_run.log 2>&1

git add .
git commit -m "auto-update: Daily Quant Report" >> logs\auto_run.log 2>&1
git push origin master >> logs\auto_run.log 2>&1

D:\python\envs\quant_engine\Scripts\mkdocs.exe gh-deploy --force >> logs\auto_run.log 2>&1

echo [%date% %time%] Task Finished >> logs\auto_run.log
echo ---------------------------------------- >> logs\auto_run.log