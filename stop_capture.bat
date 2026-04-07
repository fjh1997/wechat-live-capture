@echo off
chcp 65001 >nul
echo.
echo  正在停止所有捕获和录制进程...
echo.

REM === 关闭 FFmpeg ===
tasklist /fi "imagename eq ffmpeg.exe" 2>nul | find /i "ffmpeg.exe" >nul
if not errorlevel 1 (
    echo [1] 停止 FFmpeg 录制进程...
    taskkill /im ffmpeg.exe /f >nul 2>&1
    echo     已停止
) else (
    echo [1] 没有运行中的 FFmpeg 进程
)

REM === 关闭 mitmdump ===
tasklist /fi "imagename eq mitmdump.exe" 2>nul | find /i "mitmdump.exe" >nul
if not errorlevel 1 (
    echo [2] 停止 mitmdump 捕获进程...
    taskkill /im mitmdump.exe /f >nul 2>&1
    echo     已停止
) else (
    echo [2] 没有运行中的 mitmdump 进程
)

REM === 恢复代理 ===
echo [3] 关闭系统代理...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul
echo     已关闭

echo.
echo  ✅ 全部清理完成
echo  录像文件保存在: %~dp0recordings\
echo.
pause
