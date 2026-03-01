"""
HTTP Server for ESP32-Cam
HTTP服务器用于提供摄像头画面访问
"""

import socket
import time
from camera_setup import ESP32Camera, FRAMESIZE_VGA, FRAMESIZE_QVGA, FRAMESIZE_HD

class CameraHTTPServer:
    def __init__(self, camera, port=80):
        """
        初始化HTTP服务器

        Args:
            camera: ESP32Camera实例
            port: HTTP服务端口
        """
        self.camera = camera
        self.port = port
        self.server_socket = None
        self.running = False

        # HTTP响应头
        self.headers = {
            # MJPEG流媒体响应头
            'mjpeg_stream': """HTTP/1.1 200 OK
Content-Type: multipart/x-mixed-replace; boundary=frame
Connection: keep-alive
Cache-Control: no-cache, no-store, max-age=0, must-revalidate
Pragma: no-cache
Expires: Thu, 01 Jan 1970 00:00:00 GMT
Access-Control-Allow-Origin: *""",

            # 单张图片响应头
            'single_image': """HTTP/1.1 200 OK
Content-Type: image/jpeg
Cache-Control: no-cache""",

            # HTML页面响应头
            'html_page': """HTTP/1.1 200 OK
Content-Type: text/html; charset=UTF-8
Cache-Control: no-cache""",

            # JSON响应头
            'json_response': """HTTP/1.1 200 OK
Content-Type: application/json
Access-Control-Allow-Origin: *""",

            # 404错误响应头
            'not_found': """HTTP/1.1 404 Not Found
Content-Type: text/html; charset=UTF-8""",
        }

    def start_server(self):
        """启动HTTP服务器"""
        try:
            # 创建socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # 绑定端口
            addr = socket.getaddrinfo('0.0.0.0', self.port)[0][-1]
            self.server_socket.bind(addr)
            self.server_socket.listen(5)

            self.running = True
            print(f"HTTP服务器已启动，监听端口: {self.port}")
            print(f"访问地址: http://192.168.4.1")

            return True

        except Exception as e:
            print(f"启动HTTP服务器失败: {e}")
            return False

    def stop_server(self):
        """停止HTTP服务器"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
                print("HTTP服务器已停止")
            except:
                pass

    def handle_request(self, client_socket, client_address):
        """
        处理客户端请求

        Args:
            client_socket: 客户端socket
            client_address: 客户端地址
        """
        try:
            # 接收请求
            request = client_socket.recv(1024).decode('utf-8')
            if not request:
                return

            print(f"收到来自 {client_address} 的请求")

            # 解析请求路径
            lines = request.split('\r\n')
            if lines:
                first_line = lines[0]
                parts = first_line.split()
                if len(parts) >= 2:
                    method = parts[0]
                    path = parts[1]

                    # 路由处理
                    if method == 'GET':
                        self.handle_get_request(client_socket, path)
                    else:
                        self.send_404(client_socket)

        except Exception as e:
            print(f"处理请求异常: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass

    def handle_get_request(self, client_socket, path):
        """处理GET请求"""
        try:
            if path == '/' or path == '/index.html':
                self.send_html_page(client_socket)
            elif path == '/stream' or path == '/live':
                self.send_mjpeg_stream(client_socket)
            elif path == '/capture' or path == '/photo.jpg':
                self.send_single_image(client_socket)
            elif path == '/status':
                self.send_status(client_socket)
            elif path.startswith('/control'):
                self.handle_control(client_socket, path)
            else:
                self.send_404(client_socket)

        except Exception as e:
            print(f"处理GET请求异常: {e}")
            self.send_404(client_socket)

    def send_html_page(self, client_socket):
        """发送HTML页面"""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>ESP32 Camera</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .camera-view { margin: 20px 0; }
        img { max-width: 100%; border: 2px solid #333; }
        .controls { margin: 20px 0; }
        .btn { background: #007bff; color: white; border: none; padding: 10px 20px; margin: 5px; cursor: pointer; border-radius: 5px; }
        .btn:hover { background: #0056b3; }
        .status { background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ESP32-Camera 摄像头服务器</h1>

        <div class="camera-view">
            <h2>实时预览</h2>
            <img src="/stream" alt="Camera Stream" id="cameraStream" onerror="this.src='/capture'">
        </div>

        <div class="controls">
            <button class="btn" onclick="refreshImage()">刷新图片</button>
            <button class="btn" onclick="showStatus()">查看状态</button>
        </div>

        <div class="status" id="status">
            <strong>访问地址:</strong><br>
            • 实时流: <a href="/stream">/stream</a><br>
            • 单张图片: <a href="/capture">/capture</a><br>
            • 状态信息: <a href="/status">/status</a>
        </div>
    </div>

    <script>
        function refreshImage() {
            const img = document.getElementById('cameraStream');
            img.src = '/capture?' + new Date().getTime();
        }

        function showStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    alert('摄像头状态:\\n' + JSON.stringify(data, null, 2));
                })
                .catch(error => {
                    alert('获取状态失败: ' + error);
                });
        }
    </script>
</body>
</html>
"""

        response = f"{self.headers['html_page']}\r\nContent-Length: {len(html_content)}\r\n\r\n{html_content}"
        client_socket.send(response.encode('utf-8'))

    def send_mjpeg_stream(self, client_socket):
        """发送MJPEG流"""
        try:
            # 发送流媒体头
            client_socket.send(f"{self.headers['mjpeg_stream']}\r\n\r\n".encode('utf-8'))

            # 持续发送图像帧
            boundary = b'--frame'
            while self.running:
                try:
                    # 捕获图像
                    frame = self.camera.capture_frame()
                    if frame:
                        # 发送帧头和图像数据
                        frame_header = f"{boundary.decode()}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n"
                        client_socket.send(frame_header.encode('utf-8'))
                        client_socket.send(frame)
                        client_socket.send(b'\r\n')
                    else:
                        # 如果捕获失败，发送空帧
                        client_socket.send(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n')
                        client_socket.send(b'\r\n')

                    time.sleep(0.1)  # 控制帧率

                except Exception as e:
                    print(f"发送流数据异常: {e}")
                    break

        except Exception as e:
            print(f"MJPEG流异常: {e}")

    def send_single_image(self, client_socket):
        """发送单张图片"""
        frame = self.camera.capture_frame()
        if frame:
            response = f"{self.headers['single_image']}\r\nContent-Length: {len(frame)}\r\n\r\n"
            client_socket.send(response.encode('utf-8'))
            client_socket.send(frame)
        else:
            self.send_404(client_socket)

    def send_status(self, client_socket):
        """发送状态信息"""
        status_data = {
            "camera": self.camera.get_status(),
            "server": {
                "running": self.running,
                "port": self.port
            },
            "time": time.time()
        }

        import json
        json_str = json.dumps(status_data, indent=2)
        response = f"{self.headers['json_response']}\r\nContent-Length: {len(json_str)}\r\n\r\n{json_str}"
        client_socket.send(response.encode('utf-8'))

    def handle_control(self, client_socket, path):
        """处理控制请求"""
        try:
            # 解析控制参数，例如: /control?size=640x480&quality=10
            if '?' in path:
                params = path.split('?', 1)[1]
                param_pairs = params.split('&')

                for param in param_pairs:
                    if '=' in param:
                        key, value = param.split('=', 1)

                        if key == 'size' and value == '640x480':
                            self.camera.set_framesize(FRAMESIZE_VGA)
                        elif key == 'size' and value == '320x240':
                            self.camera.set_framesize(FRAMESIZE_QVGA)
                        elif key == 'quality':
                            try:
                                quality = int(value)
                                self.camera.set_quality(quality)
                            except:
                                pass
                        elif key == 'contrast':
                            try:
                                contrast = int(value)
                                self.camera.set_contrast(contrast)
                            except:
                                pass

                self.send_status(client_socket)
            else:
                self.send_404(client_socket)

        except Exception as e:
            print(f"控制请求处理异常: {e}")
            self.send_404(client_socket)

    def send_404(self, client_socket):
        """发送404错误"""
        error_content = """
<!DOCTYPE html>
<html>
<head><title>404 Not Found</title></head>
<body>
    <h1>404 - 页面未找到</h1>
    <p>请访问 <a href="/">首页</a> 或 <a href="/stream">实时流</a></p>
</body>
</html>
"""

        response = f"{self.headers['not_found']}\r\nContent-Length: {len(error_content)}\r\n\r\n{error_content}"
        client_socket.send(response.encode('utf-8'))

    def run(self):
        """运行服务器主循环"""
        if not self.start_server():
            return

        print("服务器正在运行，等待客户端连接...")

        while self.running:
            try:
                # 等待客户端连接
                client_socket, client_address = self.server_socket.accept()
                print(f"客户端连接: {client_address}")

                # 处理请求
                self.handle_request(client_socket, client_address)

            except Exception as e:
                if self.running:  # 只在服务器运行时打印错误
                    print(f"服务器运行异常: {e}")
                time.sleep(0.1)