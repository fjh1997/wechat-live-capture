@echo off
chcp 65001 >nul
title 安装 mitmproxy CA 证书

echo.
echo  +==========================================+
echo  :    安装 mitmproxy CA 证书 (HTTPS解密)    :
echo  +==========================================+
echo.

set CERT_DIR=%USERPROFILE%\.mitmproxy
set CERT_FILE=%CERT_DIR%\mitmproxy-ca-cert.cer

REM === 如果证书不存在，先运行一次 mitmdump 生成 ===
if not exist "%CERT_FILE%" (
    echo [1] 生成 CA 证书...
    start /min mitmdump --set listen_port=18888
    timeout /t 3 >nul
    taskkill /im mitmdump.exe /f >nul 2>&1
    echo     证书已生成
) else (
    echo [1] CA 证书已存在
)

REM === 安装证书到受信任的根证书 ===
if exist "%CERT_FILE%" (
    echo [2] 正在安装证书到系统受信任根证书库...
    echo     (可能会弹出 UAC 确认窗口，请点击"是")
    echo.
    certutil -addstore -user "Root" "%CERT_FILE%"
    if errorlevel 1 (
        echo.
        echo [!] 自动安装失败，尝试手动方式...
        echo     正在打开证书文件，请手动安装:
        echo     1. 双击证书文件
        echo     2. 点击"安装证书"
        echo     3. 选择"当前用户"
        echo     4. 选择"将所有的证书都放入下列存储"
        echo     5. 浏览 → 选择"受信任的根证书颁发机构"
        echo     6. 完成
        start "" "%CERT_FILE%"
    ) else (
        echo.
        echo  ✅ 证书安装成功！
    )
) else (
    echo [错误] 证书文件未找到: %CERT_FILE%
    echo        请先确保 mitmproxy/mitmdump 已安装
)

echo.
pause
