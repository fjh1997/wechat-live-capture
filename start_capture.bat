@echo off
chcp 65001 >nul
title 微信直播流捕获工具

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║     微信小程序直播流 捕获 ^& 录制工具     ║
echo  ╚══════════════════════════════════════════╝
echo.

REM === 检查 mitmdump ===
where mitmdump >nul 2>&1
if errorlevel 1 (
    echo [!] 未找到 mitmdump，正在安装 mitmproxy...
    pip install mitmproxy
    if errorlevel 1 (
        echo [错误] 安装失败，请手动运行: pip install mitmproxy
        pause
        exit /b 1
    )
)

REM === 检查 FFmpeg ===
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 FFmpeg，请确保已添加到系统 PATH
    pause
    exit /b 1
)

set PROXY_PORT=8080

REM === 保存原有代理设置 ===
echo [1/4] 备份当前代理设置...
for /f "tokens=3" %%a in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable 2^>nul ^| findstr ProxyEnable') do set OLD_PROXY_ENABLE=%%a
for /f "tokens=3" %%a in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer 2^>nul ^| findstr ProxyServer') do set OLD_PROXY_SERVER=%%a

REM === 设置系统代理 ===
echo [2/4] 设置系统代理 127.0.0.1:%PROXY_PORT%...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f >nul
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /t REG_SZ /d "127.0.0.1:%PROXY_PORT%" /f >nul

REM === 检查 CA 证书 ===
echo [3/4] 检查 mitmproxy CA 证书...
set CERT_PATH=%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer
if not exist "%CERT_PATH%" (
    echo.
    echo  ┌─────────────────────────────────────────────┐
    echo  │  首次使用需要安装 CA 证书才能解密 HTTPS      │
    echo  │                                             │
    echo  │  步骤:                                      │
    echo  │  1. 先启动 mitmdump 生成证书                 │
    echo  │  2. 浏览器访问 http://mitm.it               │
    echo  │  3. 点击 Windows 按钮下载并安装证书          │
    echo  │  4. 安装到"受信任的根证书颁发机构"            │
    echo  └─────────────────────────────────────────────┘
    echo.
)

REM === 创建录像目录 ===
if not exist "%~dp0recordings" mkdir "%~dp0recordings"

echo [4/4] 启动流量捕获...
echo.
echo  ┌─────────────────────────────────────────────┐
echo  │  录像保存位置: %~dp0recordings\             │
echo  │                                             │
echo  │  现在请打开 PC 微信的小程序, 开始看直播       │
echo  │  工具会自动捕获流地址并开始录制               │
echo  │                                             │
echo  │  按 Ctrl+C 停止捕获和录制                    │
echo  └─────────────────────────────────────────────┘
echo.

REM === 启动 mitmdump ===
mitmdump -s "%~dp0stream_addon.py" -p %PROXY_PORT% --ssl-insecure --set console_eventlog_verbosity=info

REM === 恢复代理设置 ===
echo.
echo 正在恢复代理设置...
if defined OLD_PROXY_ENABLE (
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d %OLD_PROXY_ENABLE% /f >nul
) else (
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul
)
if defined OLD_PROXY_SERVER (
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /t REG_SZ /d "%OLD_PROXY_SERVER%" /f >nul
)

echo [完成] 代理已恢复，录像文件在 recordings 目录
pause
