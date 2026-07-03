#!/usr/bin/env python3
import json
import subprocess
import platform
import socket
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import os
import sys

class ConnectionData:
    def __init__(self):
        self.system = platform.system()
    
    def get_local_ips(self):
        """自分のIPアドレスを取得"""
        ips = []
        try:
            # ホスト名からIPを取得
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip and local_ip not in ips:
                ips.append(local_ip)
        except:
            pass
        
        # localhost を追加
        if '127.0.0.1' not in ips:
            ips.append('127.0.0.1')
        
        return ips
    
    def get_all_connections(self):
        """netstat/ss コマンドで接続情報を取得"""
        connections = []
        
        try:
            if self.system == 'Linux':
                # ss コマンドを試行
                try:
                    result = subprocess.run(
                        ['ss', '-tun'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        connections = self._parse_ss_linux(result.stdout)
                        if connections:
                            return connections
                except:
                    pass
                
                # netstat で試行
                try:
                    result = subprocess.run(
                        ['netstat', '-tun'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        connections = self._parse_netstat_linux(result.stdout)
                except:
                    pass
            
            elif self.system == 'Windows':
                result = subprocess.run(
                    'netstat -an',
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=True
                )
                if result.returncode == 0:
                    connections = self._parse_netstat_windows(result.stdout)
            
            elif self.system == 'Darwin':  # macOS
                result = subprocess.run(
                    ['netstat', '-an'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    connections = self._parse_netstat_macos(result.stdout)
        
        except Exception as e:
            print(f"Error: {e}")
        
        return connections
    
    def _parse_ss_linux(self, output):
        """ss コマンド出力をパース"""
        connections = []
        for line in output.split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 5:
                try:
                    remote = parts[4]
                    if ':' in remote and remote != '*:*':
                        ip, port = remote.rsplit(':', 1)
                        if ip and port.isdigit():
                            connections.append({
                                'ip': ip,
                                'port': int(port),
                                'status': parts[0] if parts else 'UNKNOWN'
                            })
                except:
                    pass
        return connections
    
    def _parse_netstat_linux(self, output):
        """netstat Linux 出力をパース"""
        connections = []
        for line in output.split('\n')[2:]:
            parts = line.split()
            if len(parts) >= 6 and parts[0] in ['tcp', 'tcp6']:
                try:
                    remote = parts[4]
                    if ':' in remote and remote != '*:*':
                        ip, port = remote.rsplit(':', 1)
                        if ip and port.isdigit():
                            connections.append({
                                'ip': ip,
                                'port': int(port),
                                'status': parts[5]
                            })
                except:
                    pass
        return connections
    
    def _parse_netstat_windows(self, output):
        """netstat Windows 出力をパース"""
        connections = []
        for line in output.split('\n')[4:]:
            parts = line.split()
            if len(parts) >= 4 and parts[0] in ['TCP', 'UDP']:
                try:
                    remote = parts[2]
                    if ':' in remote and remote not in ['*:*', '0.0.0.0:0']:
                        ip, port = remote.rsplit(':', 1)
                        if ip and port.isdigit():
                            connections.append({
                                'ip': ip,
                                'port': int(port),
                                'status': parts[3] if len(parts) > 3 else 'UNKNOWN'
                            })
                except:
                    pass
        return connections
    
    def _parse_netstat_macos(self, output):
        """netstat macOS 出力をパース"""
        connections = []
        for line in output.split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 6:
                try:
                    remote = parts[4]
                    if '.' in remote and remote != '*.*' and '*' not in remote:
                        addr_parts = remote.rsplit('.', 1)
                        if len(addr_parts) == 2:
                            ip, port = addr_parts
                            if port.isdigit():
                                connections.append({
                                    'ip': ip,
                                    'port': int(port),
                                    'status': parts[5] if len(parts) > 5 else 'UNKNOWN'
                                })
                except:
                    pass
        return connections

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/api/connections':
            try:
                data = ConnectionData()
                connections = data.get_all_connections()
                local_ips = data.get_local_ips()
                
                # 重複を除去
                unique = {}
                for conn in connections:
                    key = f"{conn['ip']}:{conn['port']}"
                    if key not in unique:
                        unique[key] = conn
                
                response = {
                    'success': True,
                    'local_ips': local_ips,
                    'total': len(unique),
                    'connections': sorted(list(unique.values()), key=lambda x: x['ip'])
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': str(e),
                    'connections': [],
                    'local_ips': []
                }, ensure_ascii=False).encode())
        
        elif path == '/' or path == '/index.html':
            self.path = '/index.html'
            super().do_GET()
        else:
            super().do_GET()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")

if __name__ == '__main__':
    port = 8000
    host = '127.0.0.1'
    
    # コマンドライン引数を処理
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])
    if '--public' in sys.argv:
        host = '0.0.0.0'
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║      IP接続追跡ツール - サーバー v1.0                  ║
╚═══════════════════════════════════════════════════════════╝

🌐 開始: http://{host}:{port}
📊 ブラウザで上記URLにアクセスしてください

OS: {platform.system()}
Python: {sys.version.split()[0]}

Ctrl+C で停止
""")
    
    server = HTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 停止しました")
        server.server_close()
