"""
微信小程序直播流捕获与自动录制 v2
=================================
核心改进：
  1. 用 MPEG-TS (.ts) 格式录制，进程中断也不损坏
  2. 抓到流地址后自动关闭代理，避免观看卡顿
  3. 录制结束后自动转换为 MP4

用法：
    mitmdump -s stream_addon.py -p 8080
"""

import os
import re
import subprocess
import threading
import signal
import sys
import winreg
from datetime import datetime
from mitmproxy import http, ctx


def disable_system_proxy():
    """关闭系统代理"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        ctx.log.error(f"关闭代理失败: {e}")
        return False


class LiveStreamCapture:
    """直播流捕获与录制插件 v2"""

    STREAM_EXTENSIONS = ('.m3u8', '.flv', '.ts', '.mp4')

    STREAM_CONTENT_TYPES = {
        'application/vnd.apple.mpegurl': 'm3u8',
        'application/x-mpegurl': 'm3u8',
        'video/x-flv': 'flv',
        'video/mp2t': 'ts',
    }

    LIVE_CDN_PATTERNS = [
        r'liveplay.*\.myqcloud\.com',
        r'livepush.*\.myqcloud\.com',
        r'live.*\.qq\.com',
        r'live.*\.video\.qq\.com',
        r'.*\.livecdn\.',
        r'.*\.live\.\w+\.com',
        r'.*\.livepull\.',
        r'.*cdn.*live.*',
        r'.*live.*cdn.*',
        r'.*xiaoe-live\.com',
    ]

    def __init__(self):
        self.captured_urls = set()
        self.recording_procs = {}
        self.output_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "recordings"
        )
        os.makedirs(self.output_dir, exist_ok=True)
        self.url_log = os.path.join(self.output_dir, "captured_urls.txt")
        self.proxy_disabled = False

        ctx.log.alert("=" * 60)
        ctx.log.alert("  微信小程序直播流捕获工具 v2")
        ctx.log.alert(f"  录像保存目录: {self.output_dir}")
        ctx.log.alert("  改进: TS格式防损坏 + 自动关代理防卡顿")
        ctx.log.alert("  请打开微信小程序开始看直播...")
        ctx.log.alert("=" * 60)

    def response(self, flow: http.HTTPFlow):
        """拦截 HTTP(S) 响应，检测直播流"""
        if not flow.response:
            return

        url = flow.request.pretty_url
        content_type = flow.response.headers.get("content-type", "").lower()

        # === 检测方式1：URL 扩展名匹配 ===
        url_path = url.lower().split("?")[0]
        for ext in self.STREAM_EXTENSIONS:
            if url_path.endswith(ext):
                stype = ext.lstrip(".")
                if stype != 'ts':
                    self._on_stream_found(url, stype, "URL扩展名匹配")
                return

        # === 检测方式2：Content-Type 匹配 ===
        for ct, stype in self.STREAM_CONTENT_TYPES.items():
            if ct in content_type:
                self._on_stream_found(url, stype, "Content-Type匹配")
                return

        # === 检测方式3：响应体包含 m3u8 标识 ===
        if flow.response.content:
            try:
                body_head = flow.response.content[:1024].decode('utf-8', errors='ignore')
                if '#EXTM3U' in body_head:
                    self._on_stream_found(url, 'm3u8', "响应体包含EXTM3U")
                    return
            except Exception:
                pass

        # === 检测方式4：JSON API 响应中提取流地址 ===
        if 'json' in content_type or 'javascript' in content_type:
            self._check_json_for_streams(flow)

        # === 检测方式5：检查直播 CDN 域名 ===
        for pattern in self.LIVE_CDN_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                if any(kw in url.lower() for kw in ['live', 'stream', 'play', 'pull']):
                    self._on_stream_found(url, 'cdn_detected', "CDN域名匹配")
                    return

    def _check_json_for_streams(self, flow: http.HTTPFlow):
        """从 JSON/API 响应中提取流地址"""
        try:
            body = flow.response.content.decode('utf-8', errors='ignore')
            stream_urls = re.findall(
                r'https?://[^\s"\'\\<>]+\.(?:m3u8|flv)(?:\?[^\s"\'\\<>]*)?',
                body
            )
            for found_url in stream_urls:
                found_url = found_url.replace('\\/', '/')
                ext = 'm3u8' if '.m3u8' in found_url else 'flv'
                self._on_stream_found(found_url, ext, "API响应提取")
        except Exception:
            pass

    def _on_stream_found(self, url: str, stream_type: str, source: str):
        """发现直播流时的处理"""
        base = url.split("?")[0]
        if base in self.captured_urls:
            return
        self.captured_urls.add(base)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        ctx.log.alert("")
        ctx.log.alert("🔴" + "=" * 58)
        ctx.log.alert(f"  捕获到直播流！")
        ctx.log.alert(f"  类型:   {stream_type.upper()}")
        ctx.log.alert(f"  来源:   {source}")
        ctx.log.alert(f"  URL:    {url[:120]}{'...' if len(url) > 120 else ''}")
        ctx.log.alert("=" * 60)

        with open(self.url_log, "a", encoding="utf-8") as f:
            f.write(f"[{now_str}] [{stream_type}] [{source}]\n")
            f.write(f"  {url}\n\n")

        if stream_type in ('m3u8', 'flv', 'mp4', 'cdn_detected'):
            # ★ 关键改进：先关闭代理，再直连录制
            if not self.proxy_disabled:
                ctx.log.alert("🔧 自动关闭系统代理（避免观看卡顿）...")
                if disable_system_proxy():
                    self.proxy_disabled = True
                    ctx.log.alert("✅ 代理已关闭，微信直播将恢复流畅")
                    ctx.log.alert("   FFmpeg 将直接连接 CDN 录制")

            self._start_recording(url, stream_type)
        else:
            ctx.log.info(f"  (类型 {stream_type} 不自动录制，URL 已保存)")

    def _start_recording(self, url: str, stream_type: str):
        """
        使用 FFmpeg 录制直播流
        ★ 关键改进：先录为 .ts 格式（防中断损坏），结束后自动转 .mp4
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 录制阶段使用 .ts 格式（MPEG-TS 每个包独立，中断不损坏）
        ts_file = os.path.join(self.output_dir, f"live_{timestamp}.ts")
        mp4_file = os.path.join(self.output_dir, f"live_{timestamp}.mp4")

        # 构建 FFmpeg 命令 —— 输出 MPEG-TS
        cmd = ["ffmpeg", "-y"]

        cmd.extend([
            "-headers",
            "Referer: https://servicewechat.com\r\n"
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36\r\n",
        ])

        cmd.extend(["-i", url])
        cmd.extend([
            "-c", "copy",
            "-f", "mpegts",  # ★ 输出 MPEG-TS 格式
            ts_file,
        ])

        ctx.log.alert(f"🎬 开始录制（TS格式，防损坏）")
        ctx.log.alert(f"   录制文件: {ts_file}")
        ctx.log.alert(f"   结束后将自动转换为 MP4")
        ctx.log.alert(f"   停止: 按 Ctrl+C 或关闭此窗口")

        def _run():
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=(
                        subprocess.CREATE_NEW_PROCESS_GROUP
                        if os.name == 'nt' else 0
                    ),
                )
                self.recording_procs[url] = proc

                last_progress = ""
                for raw_line in iter(proc.stdout.readline, b''):
                    line = raw_line.decode('utf-8', errors='ignore').strip()
                    if 'size=' in line and 'time=' in line:
                        size_m = re.search(r'size=\s*(\S+)', line)
                        time_m = re.search(r'time=(\S+)', line)
                        if size_m and time_m:
                            progress = f"📹 录制中  大小: {size_m.group(1)}  时长: {time_m.group(1)}"
                            if progress != last_progress:
                                ctx.log.info(progress)
                                last_progress = progress

                proc.wait()
                ctx.log.alert(f"📼 录制结束: {ts_file}")

                # ★ 自动转换 TS → MP4
                self._convert_ts_to_mp4(ts_file, mp4_file)

            except Exception as e:
                ctx.log.error(f"❌ 录制出错: {e}")
            finally:
                self.recording_procs.pop(url, None)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _convert_ts_to_mp4(self, ts_file: str, mp4_file: str):
        """将 TS 文件转换为 MP4"""
        if not os.path.exists(ts_file):
            return
        
        file_size = os.path.getsize(ts_file)
        if file_size < 1024:  # 小于 1KB 说明没录到内容
            ctx.log.warn(f"⚠️ TS 文件过小 ({file_size} bytes)，跳过转换")
            return

        ctx.log.alert(f"🔄 正在转换 TS → MP4 ...")
        ctx.log.alert(f"   源文件大小: {file_size / 1024 / 1024:.1f} MB")

        cmd = [
            "ffmpeg", "-y",
            "-i", ts_file,
            "-c", "copy",
            "-movflags", "+faststart",
            mp4_file,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=300,
            )
            if result.returncode == 0 and os.path.exists(mp4_file):
                mp4_size = os.path.getsize(mp4_file)
                ctx.log.alert(f"✅ 转换完成: {mp4_file}")
                ctx.log.alert(f"   MP4 大小: {mp4_size / 1024 / 1024:.1f} MB")
                # 保留 .ts 备份（用户可手动删除）
                ctx.log.info(f"   TS 原始文件已保留: {ts_file}")
            else:
                ctx.log.warn(f"⚠️ 转换失败，但 TS 文件仍可播放: {ts_file}")
        except subprocess.TimeoutExpired:
            ctx.log.warn(f"⚠️ 转换超时，TS 文件仍可播放: {ts_file}")
        except Exception as e:
            ctx.log.error(f"❌ 转换出错: {e}")
            ctx.log.info(f"   TS 文件仍可正常播放: {ts_file}")


addons = [LiveStreamCapture()]
