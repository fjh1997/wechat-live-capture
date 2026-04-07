# 微信小程序直播录制工具

一键捕获微信小程序直播流地址并自动录制到本地。

## 特性

- 🔍 **自动抓流** — mitmproxy 拦截流量，自动识别 m3u8/FLV 直播流
- 📹 **自动录制** — 捕获到流地址后，FFmpeg 直连 CDN 录制
- ⚡ **不影响观看** — 抓到 URL 后自动关闭代理，直播不卡顿
- 🛡️ **防损坏** — 使用 MPEG-TS 格式录制，进程中断也不丢失内容，结束后自动转 MP4

## 依赖

- Python 3.8+
- [mitmproxy](https://mitmproxy.org/) — `pip install mitmproxy`
- [FFmpeg](https://ffmpeg.org/) — 需添加到系统 PATH

## 使用方法

### 首次使用

运行 `install_cert.bat`（管理员），安装 mitmproxy CA 证书用于 HTTPS 解密。

### 录制直播

1. 双击 `start_capture.bat`
2. 打开 PC 微信小程序，进入直播间
3. 工具自动完成：抓取流地址 → 关闭代理 → 后台录制
4. 看完直播后关闭窗口，自动转换为 MP4

录像保存在 `recordings/` 目录下。

### 紧急停止

双击 `stop_capture.bat`，停止所有进程并恢复代理设置。

## 文件说明

| 文件 | 说明 |
|------|------|
| `stream_addon.py` | mitmproxy 插件（核心：流检测 + 自动录制） |
| `start_capture.bat` | 一键启动（设代理 → 启动抓流） |
| `stop_capture.bat` | 紧急停止 + 清理代理 |
| `install_cert.bat` | 首次使用：安装 HTTPS 解密证书 |

## 原理

```
PC微信 → 系统代理 → mitmproxy(抓URL) → 关代理 → FFmpeg直连CDN录制
                                                    ↓
                                              recordings/*.ts → .mp4
```

## License

MIT
