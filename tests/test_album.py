"""
--album 公众号合集：用真实抓到的 appmsgalbum 响应离线测试翻页、结束条件、去重、风控停止、ret 错误和续跑
"""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

import wechat_downloader.album as album_module
import wechat_downloader.batch as batch_module
import wechat_downloader.downloader as downloader_module
from wechat_downloader import main as cli
from wechat_downloader.album import (
    AlbumError, AlbumListing, cache_path, list_album, load_cache, parse_album_response, parse_album_url,
)
from wechat_downloader.batch import PROGRESS_FILE
from wechat_downloader.fetch import VerificationRequired, check_article_page

from test_review_fixes import make_page

FIXTURES = Path(__file__).parent / "fixtures" / "album"
VERIFY_PAGE = (Path(__file__).parent / "fixtures" / "real" / "verify.html").read_text(encoding="utf-8")
JSON_TYPE = "application/json; charset=UTF-8"

KANLIXIANG = ("MzA3MDM3NjE5NQ==", "1375870284640911361", [f"kanlixiang-p{i}.json" for i in range(1, 7)])
RWKV = ("MzkxMDYxNzg2Nw==", "3366358796620595200", ["rwkv-p1.json", "rwkv-p2.json"])
JINFANGZI = ("Mzg3NjMzMzI2OQ==", "2857110852062199810", ["jinfangzi-p1.json", "jinfangzi-p2.json"])


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def last_cursor(text):
    items = json.loads(text)["getalbum_resp"]["article_list"]
    return items[-1]["msgid"], items[-1]["itemidx"]


class AlbumServer:
    """
    按游标回放真实响应：首页不带游标，之后每页的游标必须精确等于上一页最后一条的 msgid+itemidx，
    游标对不上时和真实接口一样回空列表（continue_flag 仍是 1）。overrides 按第几次请求替换响应。
    """

    def __init__(self, pages, overrides=None):
        self.pages = {}
        cursor = None
        for name in pages:
            text = fixture(name)
            self.pages[cursor] = text
            cursor = last_cursor(text)
        self.overrides = overrides or {}
        self.requests = []

    def __call__(self, params):
        self.requests.append(params)
        override = self.overrides.get(len(self.requests))
        if override is not None:
            return override
        cursor = (params["begin_msgid"], params["begin_itemidx"]) if "begin_msgid" in params else None
        return JSON_TYPE, self.pages.get(cursor, fixture("empty.json"))


def run(album, server=None, listing=None, **kwargs):
    biz, album_id, pages = album
    server = server or AlbumServer(pages)
    sleeps = []
    listing = list_album(server, listing or AlbumListing(biz=biz, album_id=album_id), delay=kwargs.pop("delay", 0),
                         jitter=0, sleep=sleeps.append, **kwargs)
    return listing, server, sleeps


def test_parse_album_url_accepts_pasted_forms():
    url = ("https://mp.weixin.qq.com/mp/appmsgalbum?__biz=MzA3MDM3NjE5NQ==&amp;action=getalbum"
           "&amp;album_id=1375870284640911361#wechat_redirect")
    assert parse_album_url(url) == ("MzA3MDM3NjE5NQ==", "1375870284640911361")
    assert parse_album_url("mp.weixin.qq.com/mp/appmsgalbum?__biz=MzA3MDM3NjE5NQ%3D%3D&album_id=1") == \
        ("MzA3MDM3NjE5NQ==", "1")
    with pytest.raises(album_module.WeChatError):
        parse_album_url("https://mp.weixin.qq.com/mp/appmsgalbum?__biz=MzA3MDM3NjE5NQ==&action=getalbum")
    with pytest.raises(album_module.WeChatError):
        parse_album_url("https://mp.weixin.qq.com/mp/appmsgalbum?__biz=x&album_id=abc")


def test_walks_whole_album_until_continue_flag_0():
    listing, server, sleeps = run(KANLIXIANG)
    assert listing.complete and listing.title == "李想主义" and listing.nickname == "看理想"
    assert listing.article_count == 96 and len(listing.articles) == 96
    assert len(server.requests) == 6
    assert len({(a["msgid"], a["itemidx"]) for a in listing.articles}) == 96
    assert all(p["count"] == "20" and p["f"] == "json" for p in server.requests)
    assert "begin_msgid" not in server.requests[0]
    assert (server.requests[1]["begin_msgid"], server.requests[1]["begin_itemidx"]) == ("2650931254", "1")
    # 列表请求之间至少 3 秒，即使 --delay 0
    assert sleeps == [3.0] * 5


def test_urls_are_normalized():
    listing, _, _ = run(KANLIXIANG)
    first = listing.articles[0]
    assert first["url"].startswith("https://mp.weixin.qq.com/s?__biz=MzA3MDM3NjE5NQ==&mid=2650941860&idx=1&sn=")
    assert all(u.startswith("https://") and "#" not in u for u in listing.urls)
    assert "chksm=" in first["url"]
    assert first["title"] == "胡鑫宇们，需要的不是那“五分钟”"


def test_unnumbered_album_without_pos_num():
    listing, server, _ = run(RWKV)
    assert listing.complete and len(listing.articles) == 31 == listing.article_count
    assert len(server.requests) == 2


def test_cursor_uses_last_itemidx_and_empty_list_ends():
    listing, server, _ = run(JINFANGZI)
    # p1 最后一条是次条文章（itemidx=2），游标必须带 2 才能拿到 p2
    assert (server.requests[1]["begin_msgid"], server.requests[1]["begin_itemidx"]) == ("2247514774", "2")
    # p2 之后没有更多 fixture，服务端回真实的空列表响应（continue_flag=1 但没有 article_list），应结束
    assert len(server.requests) == 3 and listing.complete
    assert len(listing.articles) == 40
    assert listing.cursor == ("2247514466", "2")


def test_dedup_and_stop_when_page_has_nothing_new():
    p1 = fixture("kanlixiang-p1.json")
    data = json.loads(p1)
    items = data["getalbum_resp"]["article_list"]
    data["getalbum_resp"]["article_list"] = items + items[:3]
    server = AlbumServer(KANLIXIANG[2], overrides={1: (JSON_TYPE, json.dumps(data, ensure_ascii=False)),
                                                   2: (JSON_TYPE, p1)})
    listing, server, _ = run(KANLIXIANG, server=server)
    assert len(listing.articles) == 10
    assert len(server.requests) == 2 and listing.complete


def test_single_article_object_is_accepted():
    data = json.loads(fixture("rwkv-p2.json"))
    data["getalbum_resp"]["article_list"] = data["getalbum_resp"]["article_list"][0]
    assert len(album_module.page_articles(parse_album_response(JSON_TYPE, json.dumps(data)))) == 1


@pytest.mark.parametrize("content_type,body", [
    ("text/html; charset=utf-8", VERIFY_PAGE),
    (JSON_TYPE, VERIFY_PAGE),
    (JSON_TYPE, ""),
])
def test_non_json_is_treated_as_risk_control(content_type, body):
    with pytest.raises(VerificationRequired):
        parse_album_response(content_type, body)


def test_risk_control_stops_and_resume_continues_from_cursor():
    saved = []
    server = AlbumServer(KANLIXIANG[2], overrides={3: ("text/html; charset=utf-8", VERIFY_PAGE)})
    listing = AlbumListing(biz=KANLIXIANG[0], album_id=KANLIXIANG[1])
    with pytest.raises(VerificationRequired):
        run(KANLIXIANG, server=server, listing=listing, on_page=lambda l: saved.append(l.to_json()))
    assert len(server.requests) == 3
    assert saved[-1]["complete"] is False and len(saved[-1]["articles"]) == 30
    resumed = AlbumListing.from_json(saved[-1])
    listing, server2, _ = run(KANLIXIANG, listing=resumed)
    assert (server2.requests[0]["begin_msgid"], server2.requests[0]["begin_itemidx"]) == ("2650911532", "1")
    assert len(server2.requests) == 4 and len(listing.articles) == 96


def test_ret_10004_means_bad_album_id():
    with pytest.raises(AlbumError, match="album_id 错误"):
        parse_album_response(JSON_TYPE, fixture("bad-album.json"))


def test_other_ret_is_explicit_error():
    with pytest.raises(AlbumError, match="ret=-3"):
        parse_album_response(JSON_TYPE, '{"base_resp":{"ret":-3,"errmsg":"no session"}}')
    with pytest.raises(AlbumError, match="ret=200003"):
        list_album(lambda p: (JSON_TYPE, '{"base_resp":{"ret":200003}}'),
                   AlbumListing(biz="b", album_id="1"), sleep=lambda s: None)


class FakeResponse:
    def __init__(self, content_type, text):
        self.headers = {"Content-Type": content_type}
        self.text = text
        self.encoding = None

    def raise_for_status(self):
        pass


class AlbumSiteFetcher:
    """同时扮演合集接口（session.get）和文章页面（get_article_html）"""

    def __init__(self, server):
        self.server = server
        self.article_requests = []
        self.session = self

    def get(self, url, params=None, **kwargs):
        assert url == album_module.ALBUM_ENDPOINT
        return FakeResponse(*self.server(params))

    def get_article_html(self, url):
        self.article_requests.append(url)
        query = parse_qs(urlsplit(url).query)
        page = make_page(f"<p>{query['mid'][0]}</p>", title=f"文章{query['mid'][0]}", biz=query["__biz"][0],
                         extra_js=f'var mid = "{query["mid"][0]}"; var idx = "{query["idx"][0]}";')
        check_article_page(page)
        return page

    def get_image(self, url):
        return b"img", "image/jpeg"


ALBUM_URL = f"https://mp.weixin.qq.com/mp/appmsgalbum?__biz={RWKV[0]}&action=getalbum&album_id={RWKV[1]}#wechat_redirect"


@pytest.fixture
def no_sleep(monkeypatch):
    sleeps = []
    for module in (album_module, batch_module, cli):
        monkeypatch.setattr(module.time, "sleep", sleeps.append)
    return sleeps


def test_cli_album_downloads_caches_and_resumes(tmp_path, monkeypatch, no_sleep, capsys):
    out_dir = tmp_path / "out"
    fetcher = AlbumSiteFetcher(AlbumServer(RWKV[2]))
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main(["--album", ALBUM_URL, "-o", str(out_dir), "--no-images"]) == 0
    assert len(fetcher.server.requests) == 2 and len(fetcher.article_requests) == 31
    assert len(list(out_dir.glob("*/*.md"))) == 31
    cache = load_cache(out_dir, *RWKV[:2])
    assert cache.complete and len(cache.articles) == 31
    progress = json.loads((out_dir / PROGRESS_FILE).read_text(encoding="utf-8"))["articles"]
    assert set(progress) == set(cache.urls)

    again = AlbumSiteFetcher(AlbumServer(RWKV[2]))
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: again)
    assert cli.main(["--album", ALBUM_URL, "-o", str(out_dir), "--no-images"]) == 0
    assert again.server.requests == [] and again.article_requests == []
    assert "使用缓存的合集列表" in capsys.readouterr().out

    refreshed = AlbumSiteFetcher(AlbumServer(RWKV[2]))
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: refreshed)
    assert cli.main(["--album", ALBUM_URL, "-o", str(out_dir), "--refresh-album", "--no-images"]) == 0
    assert len(refreshed.server.requests) == 2 and refreshed.article_requests == []


def test_cli_album_risk_control_keeps_partial_cache(tmp_path, monkeypatch, no_sleep, capsys):
    out_dir = tmp_path / "out"
    fetcher = AlbumSiteFetcher(AlbumServer(RWKV[2], overrides={2: ("text/html", VERIFY_PAGE)}))
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main(["--album", ALBUM_URL, "-o", str(out_dir)]) == 1
    assert fetcher.article_requests == []
    assert "验证页" in capsys.readouterr().out
    cached = json.loads(cache_path(out_dir, RWKV[1]).read_text(encoding="utf-8"))
    assert cached["complete"] is False and len(cached["articles"]) == 20

    fetcher = AlbumSiteFetcher(AlbumServer(RWKV[2]))
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main(["--album", ALBUM_URL, "-o", str(out_dir), "--no-images"]) == 0
    assert len(fetcher.server.requests) == 1 and fetcher.server.requests[0]["begin_msgid"] == "2247486394"
    assert len(fetcher.article_requests) == 31


def test_cli_album_bad_id_and_list_delay(tmp_path, monkeypatch, no_sleep, capsys):
    fetcher = AlbumSiteFetcher(lambda params: (JSON_TYPE, fixture("bad-album.json")))
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main(["--album", ALBUM_URL, "-o", str(tmp_path / "out")]) == 1
    assert "album_id 错误" in capsys.readouterr().out

    fetcher = AlbumSiteFetcher(AlbumServer(RWKV[2]))
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    no_sleep.clear()
    assert cli.main(["--album", ALBUM_URL, "-o", str(tmp_path / "out2"), "--no-images",
                     "--delay", "5", "--jitter", "0"]) == 0
    # 1 次翻页间隔 + 列表与首篇之间 1 次 + 31 篇之间 30 次，全部是 --delay
    assert no_sleep == [5.0] * 32


def test_cli_album_conflicts_with_other_modes(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["--album", ALBUM_URL, "--urls", str(tmp_path / "x.txt")])
    with pytest.raises(SystemExit):
        cli.main(["--album", ALBUM_URL, "https://mp.weixin.qq.com/s/abc"])
