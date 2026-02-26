"""
HTTP Server Module for ESP32-Cam V2
HTTP服务器模块 - 提供视频流和图像访问

功能:
1. MJPEG视频流服务
2. 单张图片捕获
3. 状态查询接口
4. 摄像头参数控制
5. 详细日志输出
6. 内存管理和优化
7. 流超时检测
"""

import socket
import time
import gc
import machine
from camera_setup import (
    ESP32Camera,
    FRAMESIZE_VGA, FRAMESIZE_QVGA, FRAMESIZE_HD,
    FRAMESIZE_SVGA, FRAMESIZE_XGA
)

# ==================== 内存管理配置 ====================
GC_THRESHOLD = 80000        # 可用内存低于此值时触发GC (bytes)
GC_INTERVAL = 50            # 每处理N个请求后强制GC
STREAM_TIMEOUT = 120        # 流超时时间 (秒)
STREAM_GC_INTERVAL = 30     # 流模式下每N帧执行一次GC
LOW_MEMORY_WARNING = 40000  # 低内存告警阈值 (bytes)
FRAME_DELAY = 0.08          # 帧间隔时间 (秒), 约12.5fps


def smart_gc(force=False, tag="[GC]"):
    """智能内存清理"""
    free_mem = gc.mem_free()

    if force or free_mem < GC_THRESHOLD:
        before = free_mem
        gc.collect()
        after = gc.mem_free()
        freed = after - before
        print(f"{tag} 内存清理: {before} -> {after} bytes (释放 {freed} bytes)")
        return True, after

    return False, free_mem


def check_memory():
    """检查内存状态"""
    free = gc.mem_free()
    alloc = gc.mem_alloc()
    total = free + alloc

    status = {
        "free": free,
        "alloc": alloc,
        "total": total,
        "free_percent": (free / total * 100) if total > 0 else 0,
        "warning": free < LOW_MEMORY_WARNING
    }

    if status["warning"]:
        print(f"[MEM] 低内存告警! 可用: {free} bytes ({status['free_percent']:.1f}%)")

    return status


class CameraHTTPServer:
    def __init__(self, camera, port=80, wifi_sta=None):
        """
        初始化HTTP服务器

        Args:
            camera: ESP32Camera实例
            port: HTTP服务端口
            wifi_sta: WiFiStation实例 (用于状态查询)
        """
        self.camera = camera
        self.port = port
        self.wifi_sta = wifi_sta
        self.server_socket = None
        self.running = False

        # 统计信息
        self.request_count = 0
        self.client_count = 0
        self.active_streams = 0
        self.total_frames_sent = 0
        self.gc_count = 0
        self.low_memory_count = 0
        self.start_time = time.time()

        print(f"[HTTP] HTTP服务器模块初始化")
        print(f"[HTTP] 端口: {port}")
        print(f"[HTTP] GC阈值: {GC_THRESHOLD} bytes")
        print(f"[HTTP] 流超时: {STREAM_TIMEOUT} 秒")
        print(f"[HTTP] 帧间隔: {FRAME_DELAY*1000:.0f} ms")

        # HTTP响应头模板 (预编码，减少运行时开销)
        self.headers = {
            'mjpeg_stream': (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
                "Connection: keep-alive\r\n"
                "Cache-Control: no-cache, no-store, max-age=0, must-revalidate\r\n"
                "Pragma: no-cache\r\n"
                "Access-Control-Allow-Origin: *\r\n"
            ),
            'single_image': (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: image/jpeg\r\n"
                "Cache-Control: no-cache\r\n"
                "Access-Control-Allow-Origin: *\r\n"
            ),
            'html_page': (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=UTF-8\r\n"
                "Cache-Control: no-cache\r\n"
                "Access-Control-Allow-Origin: *\r\n"
            ),
            'json_response': (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                "Access-Control-Allow-Origin: *\r\n"
            ),
            'not_found': (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/html; charset=UTF-8\r\n"
            ),
            'server_error': (
                "HTTP/1.1 500 Internal Server Error\r\n"
                "Content-Type: text/html; charset=UTF-8\r\n"
            ),
        }

        # 预编码边界标记
        self.boundary_frame = b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
        self.boundary_end = b'\r\n\r\n'
        self.frame_end = b'\r\n'

    def start_server(self):
        """启动HTTP服务器"""
        print("\n" + "=" * 50)
        print("[HTTP] 启动HTTP服务器...")
        print("=" * 50)

        try:
            # 初始内存清理
            smart_gc(force=True, tag="[HTTP]")

            # 创建socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.settimeout(1.0)

            # 绑定端口
            addr = socket.getaddrinfo('0.0.0.0', self.port)[0][-1]
            self.server_socket.bind(addr)
            self.server_socket.listen(3)  # 减少最大连接数以节省内存

            self.running = True
            print(f"[HTTP] HTTP服务器已启动，端口: {self.port}")

            return True

        except Exception as e:
            print(f"[HTTP] 启动失败: {e}")
            return False

    def stop_server(self):
        """停止HTTP服务器"""
        print("[HTTP] 停止HTTP服务器...")
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        print("[HTTP] 服务器已停止")

    def handle_request(self, client_socket, client_address):
        """处理客户端请求"""
        self.request_count += 1
        request_id = self.request_count

        print(f"\n[HTTP] 请求 #{request_id} 来自 {client_address[0]}:{client_address[1]}")

        try:
            client_socket.settimeout(5.0)
            request_data = client_socket.recv(512)  # 减小缓冲区

            if not request_data:
                return

            try:
                request = request_data.decode('utf-8')
            except:
                request = request_data.decode('latin-1')

            # 解析请求
            lines = request.split('\r\n')
            if lines:
                parts = lines[0].split()
                if len(parts) >= 2:
                    method, path = parts[0], parts[1]
                    print(f"[HTTP] {method} {path}")

                    if method == 'GET':
                        self.handle_get_request(client_socket, path, request_id)
                    else:
                        self.send_404(client_socket)

        except socket.timeout:
            print(f"[HTTP] 请求 #{request_id} 超时")
        except Exception as e:
            print(f"[HTTP] 请求 #{request_id} 异常: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass

            # 定期内存清理
            if self.request_count % GC_INTERVAL == 0:
                cleaned, _ = smart_gc(tag=f"[HTTP] 定期清理(请求#{self.request_count})")
                if cleaned:
                    self.gc_count += 1

    def handle_get_request(self, client_socket, path, request_id):
        """处理GET请求"""
        if path in ('/', '/index.html'):
            self.send_html_page(client_socket)
        elif path in ('/stream', '/live', '/video'):
            self.send_mjpeg_stream(client_socket, request_id)
        elif path in ('/capture', '/photo.jpg', '/image'):
            self.send_single_image(client_socket)
        elif path in ('/status', '/info'):
            self.send_status(client_socket)
        elif path.startswith('/control'):
            self.handle_control(client_socket, path)
        elif path == '/favicon.ico':
            self.send_404(client_socket)
        else:
            self.send_404(client_socket)

    def send_html_page(self, client_socket):
        """发送HTML页面"""
        html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32-Cam V2</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:sans-serif;background:#1a1a2e;color:#eee;padding:20px}
.container{max-width:800px;margin:0 auto}
h1{text-align:center;color:#0df;margin:20px 0}
.card{background:rgba(255,255,255,0.1);border-radius:10px;padding:15px;margin:10px 0}
.camera-view{text-align:center}
img{max-width:100%;border-radius:8px}
.btn{background:#0df;color:#000;border:none;padding:10px 20px;border-radius:20px;cursor:pointer;margin:5px}
.btn:hover{background:#09c}
.status{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:10px}
.status-item{background:rgba(0,0,0,0.3);padding:10px;border-radius:5px;text-align:center}
.status-item label{color:#0df;font-size:11px}
.status-item .value{font-size:16px;font-weight:bold;margin-top:5px}
</style>
</head>
<body>
<div class="container">
<h1>ESP32-Cam V2</h1>
<div class="card camera-view">
<img src="/stream" id="cam" onerror="this.src='/capture'">
<div style="margin-top:10px">
<button class="btn" onclick="document.getElementById('cam').src='/stream?'+Date.now()">刷新流</button>
<button class="btn" onclick="document.getElementById('cam').src='/capture?'+Date.now()">抓拍</button>
<button class="btn" onclick="fetch('/status').then(r=>r.json()).then(d=>alert(JSON.stringify(d,null,2)))">状态</button>
</div>
</div>
<div class="card">
<div class="status">
<div class="status-item"><label>内存</label><div class="value" id="mem">--</div></div>
<div class="status-item"><label>帧数</label><div class="value" id="frames">--</div></div>
<div class="status-item"><label>流</label><div class="value" id="streams">--</div></div>
</div>
</div>
</div>
<script>
setInterval(()=>fetch('/status').then(r=>r.json()).then(d=>{
if(d.memory)document.getElementById('mem').textContent=Math.round(d.memory.free/1024)+'KB';
if(d.server){document.getElementById('frames').textContent=d.server.total_frames||0;document.getElementById('streams').textContent=d.server.active_streams||0}
}).catch(()=>{}),3000);
</script>
</body>
</html>"""

        response = self.headers['html_page'] + f"Content-Length: {len(html)}\r\n\r\n{html}"
        client_socket.sendall(response.encode('utf-8'))

    def send_mjpeg_stream(self, client_socket, request_id):
        """发送MJPEG流 (优化版)"""
        print(f"[HTTP] 开始流 #{request_id}")

        self.active_streams += 1
        frame_count = 0
        stream_start = time.time()
        last_gc_frame = 0
        consecutive_errors = 0
        MAX_ERRORS = 5  # 连续错误上限

        try:
            # 发送流头
            client_socket.sendall((self.headers['mjpeg_stream'] + "\r\n").encode('utf-8'))

            # 设置socket超时
            client_socket.settimeout(5.0)

            while self.running:
                # 检查超时
                if time.time() - stream_start > STREAM_TIMEOUT:
                    print(f"[HTTP] 流 #{request_id} 超时断开")
                    break

                # 检查内存
                mem_status = check_memory()
                if mem_status["warning"]:
                    self.low_memory_count += 1
                    smart_gc(force=True, tag=f"[HTTP] 流#{request_id} 低内存")

                try:
                    # 捕获帧
                    frame = self.camera.capture_frame()

                    if frame:
                        consecutive_errors = 0  # 重置错误计数
                        frame_count += 1
                        self.total_frames_sent += 1

                        # 发送帧 (优化: 减少拼接操作)
                        frame_len = str(len(frame)).encode()
                        client_socket.sendall(self.boundary_frame + frame_len + self.boundary_end)
                        client_socket.sendall(frame)
                        client_socket.sendall(self.frame_end)

                        # 每30帧清理内存
                        if frame_count - last_gc_frame >= STREAM_GC_INTERVAL:
                            smart_gc(force=True, tag=f"[HTTP] 流#{request_id} 帧清理")
                            last_gc_frame = frame_count

                        # 每50帧打印状态
                        if frame_count % 50 == 0:
                            elapsed = time.time() - stream_start
                            fps = frame_count / elapsed if elapsed > 0 else 0
                            print(f"[HTTP] 流#{request_id}: {frame_count}帧, {fps:.1f}fps, 内存:{gc.mem_free()}")

                    else:
                        consecutive_errors += 1
                        print(f"[HTTP] 流#{request_id}: 捕获失败 ({consecutive_errors}/{MAX_ERRORS})")

                        if consecutive_errors >= MAX_ERRORS:
                            print(f"[HTTP] 流#{request_id}: 连续错误过多，断开")
                            break

                        time.sleep(0.1)
                        continue

                    # 帧间隔控制
                    time.sleep(FRAME_DELAY)

                except socket.timeout:
                    print(f"[HTTP] 流#{request_id}: Socket超时")
                    break
                except OSError as e:
                    print(f"[HTTP] 流#{request_id}: 连接断开 ({e})")
                    break
                except Exception as e:
                    consecutive_errors += 1
                    print(f"[HTTP] 流#{request_id}: 发送错误 ({e})")
                    if consecutive_errors >= MAX_ERRORS:
                        break
                    time.sleep(0.1)

        except Exception as e:
            print(f"[HTTP] 流#{request_id}: 异常 ({e})")
        finally:
            self.active_streams -= 1
            elapsed = time.time() - stream_start
            avg_fps = frame_count / elapsed if elapsed > 0 else 0
            print(f"[HTTP] 流#{request_id} 结束: {frame_count}帧, {elapsed:.0f}秒, {avg_fps:.1f}fps")

            # 流结束后清理内存
            smart_gc(force=True, tag=f"[HTTP] 流#{request_id} 结束清理")

    def send_single_image(self, client_socket):
        """发送单张图片"""
        frame = self.camera.capture_frame()
        if frame:
            header = self.headers['single_image'] + f"Content-Length: {len(frame)}\r\n\r\n"
            client_socket.sendall(header.encode('utf-8'))
            client_socket.sendall(frame)
            print(f"[HTTP] 图片已发送 ({len(frame)} bytes)")
        else:
            self.send_500(client_socket, "Capture failed")

    def send_status(self, client_socket):
        """发送状态信息"""
        mem_status = check_memory()

        status = {
            "camera": self.camera.get_status(),
            "server": {
                "running": self.running,
                "port": self.port,
                "uptime": round(time.time() - self.start_time, 1),
                "request_count": self.request_count,
                "client_count": self.client_count,
                "active_streams": self.active_streams,
                "total_frames": self.total_frames_sent,
                "gc_count": self.gc_count,
                "low_memory_count": self.low_memory_count
            },
            "wifi": self.wifi_sta.get_status() if self.wifi_sta else None,
            "memory": mem_status
        }

        import json
        json_str = json.dumps(status)
        response = self.headers['json_response'] + f"Content-Length: {len(json_str)}\r\n\r\n{json_str}"
        client_socket.sendall(response.encode('utf-8'))

    def handle_control(self, client_socket, path):
        """处理控制请求"""
        if '?' not in path:
            help_data = {"usage": "/control?size=640x480&quality=10", "sizes": ["320x240", "640x480", "800x600"], "quality": "1-31"}
            import json
            json_str = json.dumps(help_data)
            response = self.headers['json_response'] + f"Content-Length: {len(json_str)}\r\n\r\n{json_str}"
            client_socket.sendall(response.encode('utf-8'))
            return

        params = {}
        for param in path.split('?', 1)[1].split('&'):
            if '=' in param:
                k, v = param.split('=', 1)
                params[k] = v

        print(f"[HTTP] 控制: {params}")

        if 'size' in params:
            size_map = {'320x240': FRAMESIZE_QVGA, '640x480': FRAMESIZE_VGA, '800x600': FRAMESIZE_SVGA, '1280x720': FRAMESIZE_HD}
            if params['size'] in size_map:
                self.camera.set_framesize(size_map[params['size']])

        for p, setter in [('quality', self.camera.set_quality), ('contrast', self.camera.set_contrast),
                          ('brightness', self.camera.set_brightness), ('saturation', self.camera.set_saturation)]:
            if p in params:
                try:
                    setter(int(params[p]))
                except:
                    pass

        self.send_status(client_socket)

    def send_404(self, client_socket):
        """发送404错误"""
        html = "<html><body><h1>404</h1><a href='/'>Home</a></body></html>"
        response = self.headers['not_found'] + f"Content-Length: {len(html)}\r\n\r\n{html}"
        client_socket.sendall(response.encode('utf-8'))

    def send_500(self, client_socket, msg="Error"):
        """发送500错误"""
        html = f"<html><body><h1>500</h1><p>{msg}</p></body></html>"
        response = self.headers['server_error'] + f"Content-Length: {len(html)}\r\n\r\n{html}"
        client_socket.sendall(response.encode('utf-8'))

    def run(self):
        """运行服务器主循环"""
        if not self.start_server():
            return False

        print("\n" + "=" * 50)
        print("[HTTP] 服务器运行中...")
        print("=" * 50)

        last_status_time = time.time()
        STATUS_INTERVAL = 60  # 每60秒打印一次状态

        while self.running:
            try:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    self.client_count += 1
                    self.handle_request(client_socket, client_address)

                except socket.timeout:
                    # 定期状态打印和内存检查
                    now = time.time()
                    if now - last_status_time > STATUS_INTERVAL:
                        mem = check_memory()
                        print(f"[HTTP] 状态: 请求={self.request_count}, 流={self.active_streams}, "
                              f"帧={self.total_frames_sent}, 内存={mem['free']}({mem['free_percent']:.0f}%)")
                        last_status_time = now

                        # 定期内存清理
                        if mem['free'] < GC_THRESHOLD:
                            smart_gc(force=True, tag="[HTTP] 定期清理")
                            self.gc_count += 1

                    continue
                except OSError:
                    continue

            except Exception as e:
                if self.running:
                    print(f"[HTTP] 运行异常: {e}")
                time.sleep(0.1)

        print("[HTTP] 主循环结束")
        return True
