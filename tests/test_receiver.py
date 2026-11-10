import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from wechat_downloader.receiver import DownloadQueue, is_article_url, make_handler

ARTICLE = "https://mp.weixin.qq.com/s/abc123"


@pytest.mark.parametrize("url, ok", [
    (ARTICLE, True),
    ("https://mp.weixin.qq.com/s?__biz=MzA&mid=1&idx=1&sn=x", True),
    ("http://mp.weixin.qq.com/s/abc", False),
    ("https://mp.weixin.qq.com.evil.com/s/abc", False),
    ("https://mp.weixin.qq.com/mp/profile_ext?action=home", False),
    ("file:///etc/passwd", False),
])
def test_is_article_url(url, ok):
    assert is_article_url(url) is ok


@pytest.fixture
def server():
    received = []
    jobs = DownloadQueue(lambda url: received.append(url) or 0)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(jobs))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}", jobs, received
    httpd.shutdown()
    httpd.server_close()


def post(base, payload, origin=None):
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(base + "/download", data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read()), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), e.headers


def test_extension_origin_is_queued(server):
    base, jobs, received = server
    status, body, headers = post(base, {"url": ARTICLE}, origin="chrome-extension://abcdef")
    jobs.join()
    assert status == 202 and body["ok"]
    assert headers["Access-Control-Allow-Origin"] == "chrome-extension://abcdef"
    assert received == [ARTICLE]


def test_web_page_origin_is_rejected(server):
    base, jobs, received = server
    status, body, _ = post(base, {"url": ARTICLE}, origin="https://evil.example")
    jobs.join()
    assert status == 403
    assert received == []


def test_non_article_url_is_rejected(server):
    base, jobs, received = server
    status, body, _ = post(base, {"url": "https://example.com/s/x"})
    jobs.join()
    assert status == 400 and not body["ok"]
    assert received == []


def test_ping(server):
    base, _, _ = server
    with urllib.request.urlopen(base + "/ping") as resp:
        assert json.loads(resp.read()) == {"ok": True}
