"""
本地链接接收服务：浏览器扩展把当前文章链接 POST 过来，这里排队交给命令行下载

    python -m wechat_downloader.receiver -o ~/Documents/公众号
"""
import argparse
import json
import queue
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, List, Optional
from urllib.parse import urlsplit

DEFAULT_PORT = 4546
MAX_BODY = 8192


def is_article_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname == "mp.weixin.qq.com" and parts.path.startswith("/s")


def run_cli(url: str, output_dir: str) -> int:
    # 走命令行而不是直接调用下载函数，接收端只依赖 CLI 参数这一层稳定接口
    cmd = [sys.executable, "-m", "wechat_downloader.main", url, "-o", output_dir]
    return subprocess.call(cmd)


class DownloadQueue:
    """单线程逐篇下载，避免并发请求触发微信的验证页"""

    def __init__(self, runner: Callable[[str], int]):
        self._runner = runner
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()

    def put(self, url: str) -> int:
        self._queue.put(url)
        return self._queue.qsize()

    def join(self) -> None:
        self._queue.join()

    def _work(self) -> None:
        while True:
            url = self._queue.get()
            try:
                self._runner(url)
            except Exception as e:  # 一篇失败不影响后面的链接
                print(f"✗ {url}\n    {e}")
            finally:
                self._queue.task_done()


def make_handler(jobs: DownloadQueue):
    class Handler(BaseHTTPRequestHandler):
        def _allowed_origin(self) -> Optional[str]:
            # 普通网页也能向 127.0.0.1 发 POST，只接受扩展（或无 Origin 的本地工具如 curl）
            origin = self.headers.get("Origin")
            if origin is None or origin.startswith(("chrome-extension://", "moz-extension://")):
                return origin or ""
            return None

        def _reply(self, status: int, payload: dict, origin: str = "") -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            origin = self._allowed_origin()
            if origin is None:
                self._reply(403, {"ok": False, "error": "forbidden origin"})
                return
            self.send_response(204)
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "POST, GET")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            origin = self._allowed_origin()
            if origin is None:
                self._reply(403, {"ok": False, "error": "forbidden origin"})
            elif self.path == "/ping":
                self._reply(200, {"ok": True}, origin)
            else:
                self._reply(404, {"ok": False, "error": "not found"}, origin)

        def do_POST(self):
            origin = self._allowed_origin()
            if origin is None:
                self._reply(403, {"ok": False, "error": "forbidden origin"})
                return
            if self.path != "/download":
                self._reply(404, {"ok": False, "error": "not found"}, origin)
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if not 0 < length <= MAX_BODY:
                self._reply(400, {"ok": False, "error": "bad body"}, origin)
                return
            try:
                url = json.loads(self.rfile.read(length)).get("url", "")
            except (ValueError, AttributeError):
                url = ""
            if not isinstance(url, str) or not is_article_url(url):
                self._reply(400, {"ok": False, "error": "只接受 https://mp.weixin.qq.com/s 开头的文章链接"}, origin)
                return
            pending = jobs.put(url)
            print(f"收到链接（队列 {pending}）: {url}", flush=True)
            self._reply(202, {"ok": True, "queued": pending}, origin)

        def log_message(self, format, *args):
            pass

    return Handler


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="接收浏览器扩展发来的文章链接并下载为 Markdown")
    parser.add_argument("--output", "-o", default="downloads", help="输出目录（默认: downloads）")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help=f"监听端口（默认: {DEFAULT_PORT}）")
    parser.add_argument("--interval", type=float, default=2.0, help="每篇之间的间隔秒数（默认: 2）")
    args = parser.parse_args(argv)

    def runner(url: str) -> int:
        code = run_cli(url, args.output)
        time.sleep(max(args.interval, 0))
        return code

    jobs = DownloadQueue(runner)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(jobs))
    print(f"正在监听 http://127.0.0.1:{args.port} ，文章保存到 {args.output}（Ctrl+C 退出）", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
