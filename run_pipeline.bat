@echo off
:: 1. 声明 UTF-8 编码，防止后台运行时的中文日志变成乱码
chcp 65001 >nul

:: 2. 动态切换到脚本所在的当前绝对路径（完美避开直接写中文路径带来的乱码崩溃）
cd /d "%~dp0"

:: 3. 注入局部环境变量（代理与时间戳）
set http_proxy=http://127.0.0.1:7890
set https_proxy=http://127.0.0.1:7890
echo [%date% %time%] 开始执行无人值守任务 >> logs\auto_run.log

:: 4. 运行 Python 数据管道与 AI 分析
D:\python\envs\quant_engine\python.exe src\fetcher.py >> logs\auto_run.log 2>&1
D:\python\envs\quant_engine\python.exe src\analyzer.py >> logs\auto_run.log 2>&1

:: 5. 源码级别 Git 备份 (使用 git add . 自动匹配并遵守 .gitignore 规则)
git add .
git commit -m "auto-update: 每日量化研报自动化构建" >> logs\auto_run.log 2>&1
git push origin master >> logs\auto_run.log 2>&1

:: 6. 触发 MkDocs 静态编译与公网发布
D:\python\envs\quant_engine\Scripts\mkdocs.exe gh-deploy --force >> logs\auto_run.log 2>&1

:: 7. 封账
echo [%date% %time%] 全链路部署完毕 >> logs\auto_run.log
echo ---------------------------------------- >> logs\auto_run.log