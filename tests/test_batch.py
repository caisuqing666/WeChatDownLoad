"""
--urls 链接清单批量下载：跳过已下载、中断后续跑、验证页停止、限速、进度文件
"""
import json
import os
from pathlib import Path

import pytest

import wechat_downloader.batch as batch_module
import wechat_downloader.downloader as downloader_module
from wechat_downloader import main as cli
from wechat_downloader.batch import (
    PROGRESS_FILE, Progress, download_url_list, find_existing, read_url_file,
)
from wechat_downloader.downloader import ArticleDownloader, RollbackError, link_article_id
from wechat_downloader.fetch import ArticleUnavailable, check_article_page

from test_review_fixes import make_page

BIZ = "MzI4NjAxNjY4Nw=="
VERIFY_PAGE = (Path(__file__).parent / "fixtures" / "real" / "verify.html").read_text(encoding="utf-8")


def long_url(mid, idx=1, extra="&sn=abc"):
    return f"https://mp.weixin.qq.com/s?__biz={BIZ}&mid={mid}&idx={idx}{extra}"


def page_for(mid, title=None):
    return make_page(f"<p>正文 {mid}</p>", title=title or f"文章{mid}", extra_js=f'var mid = "{mid}"; var idx = "1";')


class MapFetcher:
    """按链接返回页面；值是异常时抛出，值是 str 时按真实流程检查验证页"""

    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def get_article_html(self, url):
        self.requests.append(url)
        value = self.pages[url]
        if isinstance(value, BaseException):
            raise value
        check_article_page(value)
        return value

    def get_image(self, url):
        return b"img", "image/jpeg"


URLS = [long_url(101), "https://mp.weixin.qq.com/s/Short102", long_url(103)]


def pages(**overrides):
    result = {URLS[0]: page_for(101), URLS[1]: page_for(102), URLS[2]: page_for(103)}
    result.update({URLS[int(k[1:])]: v for k, v in overrides.items()})
    return result


def run(tmp_path, fetcher, urls=URLS, **kw):
    kw.setdefault("delay", 0)
    kw.setdefault("jitter", 0)
    download_images = kw.pop("download_images", True)
    downloader = ArticleDownloader(output_dir=str(tmp_path), fetcher=fetcher, download_images=download_images)
    return download_url_list(downloader, urls, **kw)


def load_progress(tmp_path):
    return json.loads((tmp_path / PROGRESS_FILE).read_text(encoding="utf-8"))


# ---- 读取链接清单 ----

def test_read_url_file_skips_blank_comments_and_duplicates(tmp_path):
    links = tmp_path / "links.txt"
    links.write_text(
        "\ufeff# 我的收藏\n"
        "\n"
        f"  {long_url(1)}  \n"
        "https://mp.weixin.qq.com/s/AbC\n"
        "   # 缩进的注释\n"
        "http://mp.weixin.qq.com/s/AbC#wechat_redirect\n"
        f"{long_url(1, extra='&amp;sn=abc&amp;chksm=zz')}\n"
        f"{long_url(1, idx=2)}\n",
        encoding="utf-8",
    )
    assert read_url_file(str(links)) == [
        long_url(1), "https://mp.weixin.qq.com/s/AbC", long_url(1, idx=2),
    ]


def test_link_article_id_matches_id_of_downloaded_file(tmp_path):
    result = ArticleDownloader(output_dir=str(tmp_path), fetcher=MapFetcher(pages())).download(URLS[0])
    assert result.path.stem.endswith("_" + link_article_id(URLS[0]))
    assert link_article_id("https://mp.weixin.qq.com/s/Short102") == ""
    assert link_article_id(long_url(5)) == link_article_id(long_url(5, extra="&chksm=1")) != link_article_id(long_url(5, 2))


# ---- 正常下载与进度文件 ----

def test_downloads_all_and_writes_progress(tmp_path):
    fetcher = MapFetcher(pages())
    result = run(tmp_path, fetcher)
    assert (result.downloaded, result.skipped, result.failed, result.stopped) == (3, 0, [], None)
    data = load_progress(tmp_path)
    assert data["version"] == 1
    assert set(data["articles"]) == set(URLS)
    for url in URLS:
        entry = data["articles"][url]
        assert entry["status"] == "done"
        path = tmp_path / entry["path"]
        assert path.is_file() and path.stem.endswith("_" + entry["id"])
    assert data["articles"][URLS[0]]["id"] == link_article_id(URLS[0])
    assert data["articles"][URLS[1]]["title"] == "文章102"
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


def test_second_run_skips_everything_without_requests_or_sleep(tmp_path):
    run(tmp_path, MapFetcher(pages()))
    fetcher = MapFetcher({})
    sleeps = []
    result = run(tmp_path, fetcher, delay=3, jitter=2, sleep=sleeps.append, uniform=lambda a, b: 1)
    assert (result.downloaded, result.skipped) == (0, 3)
    assert fetcher.requests == [] and sleeps == []


def test_long_link_skipped_by_existing_file_without_progress(tmp_path):
    run(tmp_path, MapFetcher(pages()))
    (tmp_path / PROGRESS_FILE).unlink()
    fetcher = MapFetcher(pages())
    result = run(tmp_path, fetcher)
    assert fetcher.requests == [URLS[1]]
    assert (result.downloaded, result.skipped) == (1, 2)
    assert load_progress(tmp_path)["articles"][URLS[0]]["status"] == "done"
    assert find_existing(tmp_path, URLS[2]) is not None


def test_done_entry_whose_file_was_deleted_is_downloaded_again(tmp_path):
    run(tmp_path, MapFetcher(pages()))
    md = tmp_path / load_progress(tmp_path)["articles"][URLS[1]]["path"]
    md.unlink()
    fetcher = MapFetcher(pages())
    result = run(tmp_path, fetcher)
    assert fetcher.requests == [URLS[1]] and result.downloaded == 1
    assert md.is_file()


def test_corrupt_progress_file_is_ignored(tmp_path, capsys):
    (tmp_path / PROGRESS_FILE).write_text("{坏掉的", encoding="utf-8")
    result = run(tmp_path, MapFetcher(pages()))
    assert result.downloaded == 3
    assert "无法读取" in capsys.readouterr().out
    assert len(load_progress(tmp_path)["articles"]) == 3


def test_progress_save_is_atomic(tmp_path, monkeypatch):
    progress = Progress(tmp_path)
    progress.articles["a"] = {"status": "done", "path": "x.md"}
    progress.save()
    before = (tmp_path / PROGRESS_FILE).read_text(encoding="utf-8")

    def broken_replace(src, dst):
        raise KeyboardInterrupt

    monkeypatch.setattr(batch_module.os, "replace", broken_replace)
    progress.articles["b"] = {"status": "done", "path": "y.md"}
    with pytest.raises(KeyboardInterrupt):
        progress.save()
    assert (tmp_path / PROGRESS_FILE).read_text(encoding="utf-8") == before
    assert [p.name for p in tmp_path.iterdir()] == [PROGRESS_FILE]


# ---- 中断后续跑 ----

def test_interrupt_midway_then_resume(tmp_path, capsys):
    fetcher = MapFetcher(pages(u1=KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        run(tmp_path, fetcher)
    assert "进度已保存" in capsys.readouterr().out
    assert set(load_progress(tmp_path)["articles"]) == {URLS[0]}
    assert not [p for p in tmp_path.rglob("*") if p.name.startswith(".") and p.name != PROGRESS_FILE]

    fetcher = MapFetcher(pages())
    result = run(tmp_path, fetcher)
    assert fetcher.requests == URLS[1:]
    assert (result.downloaded, result.skipped) == (2, 1)
    assert {e["status"] for e in load_progress(tmp_path)["articles"].values()} == {"done"}


def test_interrupt_during_save_keeps_progress_and_old_files(tmp_path, monkeypatch):
    run(tmp_path, MapFetcher(pages()), urls=URLS[:1])
    real_replace = os.replace

    def interrupt_on_md(src, dst):
        if str(dst).endswith(".md"):
            raise KeyboardInterrupt
        return real_replace(src, dst)

    monkeypatch.setattr(downloader_module.os, "replace", interrupt_on_md)
    with pytest.raises(KeyboardInterrupt):
        run(tmp_path, MapFetcher(pages()))
    data = load_progress(tmp_path)
    assert set(data["articles"]) == {URLS[0]}
    assert len(list(tmp_path.rglob("*.md"))) == 1


def test_cli_interrupt_exits_130_and_resumes(tmp_path, monkeypatch, capsys):
    links = tmp_path / "links.txt"
    links.write_text("\n".join(URLS), encoding="utf-8")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(batch_module.time, "sleep", lambda s: None)
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: MapFetcher(pages(u2=KeyboardInterrupt())))
    assert cli.main(["--urls", str(links), "-o", str(out_dir)]) == 130
    fetcher = MapFetcher(pages())
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main(["--urls", str(links), "-o", str(out_dir)]) == 0
    assert fetcher.requests == [URLS[2]]
    assert "新下载 1 篇，跳过 2 篇，失败 0 篇" in capsys.readouterr().out


# ---- 验证页立即停止 ----

def test_verification_page_stops_immediately_and_keeps_progress(tmp_path):
    fetcher = MapFetcher(pages(u1=VERIFY_PAGE))
    result = run(tmp_path, fetcher)
    assert fetcher.requests == URLS[:2]
    assert result.stopped and "环境异常" in result.stopped
    assert (result.downloaded, result.remaining) == (1, 2)
    assert set(load_progress(tmp_path)["articles"]) == {URLS[0]}

    fetcher = MapFetcher(pages())
    result = run(tmp_path, fetcher)
    assert fetcher.requests == URLS[1:] and result.stopped is None


def test_cli_verification_page_exit_1_with_retry_hint(tmp_path, monkeypatch, capsys):
    links = tmp_path / "links.txt"
    links.write_text("\n".join(URLS), encoding="utf-8")
    monkeypatch.setattr(batch_module.time, "sleep", lambda s: None)
    fetcher = MapFetcher(pages(u0=VERIFY_PAGE))
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main(["--urls", str(links), "-o", str(tmp_path / "out")]) == 1
    out = capsys.readouterr().out
    assert fetcher.requests == URLS[:1]
    assert "还有 3 篇未处理" in out and "稍后" in out


# ---- 其他失败：记录后继续 ----

def test_other_failures_are_recorded_and_retried_next_time(tmp_path, capsys):
    fetcher = MapFetcher(pages(u1=ArticleUnavailable("文章不可用：该内容已被发布者删除"), u2=OSError("磁盘满")))
    result = run(tmp_path, fetcher)
    assert fetcher.requests == URLS
    assert result.downloaded == 1 and [u for u, _ in result.failed] == URLS[1:]
    entry = load_progress(tmp_path)["articles"][URLS[1]]
    assert entry["status"] == "failed" and "已被发布者删除" in entry["error"] and entry["attempts"] == 1

    fetcher = MapFetcher(pages(u1=ArticleUnavailable("文章不可用：该内容已被发布者删除")))
    result = run(tmp_path, fetcher)
    assert fetcher.requests == URLS[1:]
    assert result.downloaded == 1 and len(result.failed) == 1
    assert load_progress(tmp_path)["articles"][URLS[1]]["attempts"] == 2


def test_cli_summary_lists_failures(tmp_path, monkeypatch, capsys):
    links = tmp_path / "links.txt"
    links.write_text("\n".join(URLS), encoding="utf-8")
    monkeypatch.setattr(batch_module.time, "sleep", lambda s: None)
    fetcher = MapFetcher(pages(u1=ArticleUnavailable("文章不可用：内容已被删除")))
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main(["--urls", str(links), "-o", str(tmp_path / "out")]) == 1
    out = capsys.readouterr().out
    assert "共 3 篇，新下载 2 篇，跳过 0 篇，失败 1 篇" in out
    assert URLS[1] in out.split("失败的文章")[1]


def test_rollback_error_stops_the_batch(tmp_path):
    fetcher = MapFetcher(pages(u1=RollbackError("回滚也失败")))
    with pytest.raises(RollbackError):
        run(tmp_path, fetcher)
    assert fetcher.requests == URLS[:2]
    assert set(load_progress(tmp_path)["articles"]) == {URLS[0]}


def test_interrupted_ordinary_error_is_not_swallowed(tmp_path):
    error = PermissionError("拒绝访问")
    error.interrupted = True
    fetcher = MapFetcher(pages(u0=error))
    with pytest.raises(PermissionError):
        run(tmp_path, fetcher)
    assert fetcher.requests == URLS[:1]


# ---- 限速 ----

def test_sleeps_between_requests_with_jitter(tmp_path):
    sleeps, jitter_calls = [], []

    def uniform(a, b):
        jitter_calls.append((a, b))
        return 0.5

    run(tmp_path, MapFetcher(pages()), delay=3, jitter=2, sleep=sleeps.append, uniform=uniform)
    assert sleeps == [3.5, 3.5]
    assert jitter_calls == [(0, 2), (0, 2)]


def test_skipped_articles_do_not_sleep(tmp_path):
    run(tmp_path, MapFetcher(pages()), urls=URLS[1:2])
    sleeps = []
    fetcher = MapFetcher(pages())
    run(tmp_path, fetcher, delay=3, jitter=0, sleep=sleeps.append)
    assert fetcher.requests == [URLS[0], URLS[2]]
    assert sleeps == [3]


def test_zero_delay_never_sleeps(tmp_path):
    sleeps = []
    run(tmp_path, MapFetcher(pages()), delay=0, jitter=0, sleep=sleeps.append)
    assert sleeps == []


def test_cli_passes_delay_and_jitter(tmp_path, monkeypatch):
    links = tmp_path / "links.txt"
    links.write_text("\n".join(URLS), encoding="utf-8")
    sleeps = []
    monkeypatch.setattr(batch_module.time, "sleep", sleeps.append)
    monkeypatch.setattr(batch_module.random, "uniform", lambda a, b: b)
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: MapFetcher(pages()))
    assert cli.main(["--urls", str(links), "-o", str(tmp_path / "out"), "--delay", "5", "--jitter", "1.5"]) == 0
    assert sleeps == [6.5, 6.5]


def test_cli_default_delay_is_a_few_seconds_with_jitter(tmp_path, monkeypatch):
    links = tmp_path / "links.txt"
    links.write_text("\n".join(URLS[:2]), encoding="utf-8")
    sleeps, jitter_calls = [], []
    monkeypatch.setattr(batch_module.time, "sleep", sleeps.append)
    monkeypatch.setattr(batch_module.random, "uniform", lambda a, b: jitter_calls.append((a, b)) or 0)
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: MapFetcher(pages()))
    assert cli.main(["--urls", str(links), "-o", str(tmp_path / "out")]) == 0
    assert sleeps == [3.0] and jitter_calls == [(0, 2.0)]


# ---- 命令行参数 ----

def test_cli_rejects_urls_with_positional_links(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--urls", "links.txt", URLS[0]])
    assert exc.value.code == 2


def test_cli_rejects_negative_delay(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["--urls", "links.txt", "--delay", "-1"])


def test_cli_missing_or_empty_links_file(tmp_path, capsys):
    assert cli.main(["--urls", str(tmp_path / "nope.txt"), "-o", str(tmp_path)]) == 1
    empty = tmp_path / "empty.txt"
    empty.write_text("# 只有注释\n\n", encoding="utf-8")
    assert cli.main(["--urls", str(empty), "-o", str(tmp_path)]) == 1
    assert "没有文章链接" in capsys.readouterr().out


# ---- 缺图：记为 partial，重跑补齐 ----

IMG_A = "https://mmbiz.qpic.cn/a/640?wx_fmt=png"
IMG_B = "https://mmbiz.qpic.cn/b/640?wx_fmt=jpeg"


def page_with_images(mid):
    content = f'<p>正文 {mid}</p><p><img data-src="{IMG_A}"></p><p><img data-src="{IMG_B}"></p>'
    return make_page(content, title=f"图文{mid}", extra_js=f'var mid = "{mid}"; var idx = "1";')


class ImageFetcher(MapFetcher):
    def __init__(self, pages, broken=()):
        super().__init__(pages)
        self.broken = set(broken)
        self.image_requests = []

    def get_image(self, url):
        self.image_requests.append(url)
        if url in self.broken:
            raise ArticleUnavailable("下载图片失败：404")
        return b"img:" + url.encode(), "image/jpeg"


IMG_URLS = [long_url(201), "https://mp.weixin.qq.com/s/Short202"]


def image_pages():
    return {IMG_URLS[0]: page_with_images(201), IMG_URLS[1]: page_with_images(202)}


def md_of(tmp_path, url):
    return tmp_path / load_progress(tmp_path)["articles"][url]["path"]


def test_failed_images_recorded_as_partial_then_completed_on_rerun(tmp_path):
    result = run(tmp_path, ImageFetcher(image_pages(), broken={IMG_B}), urls=IMG_URLS)
    assert result.downloaded == 2 and [u for u, _, _ in result.partial] == IMG_URLS
    for url in IMG_URLS:
        entry = load_progress(tmp_path)["articles"][url]
        assert entry["status"] == "partial"
        assert entry["missing_images"] == 1 and entry["failed_images"] == [IMG_B]
        assert IMG_B in md_of(tmp_path, url).read_text(encoding="utf-8")

    fetcher = ImageFetcher(image_pages())
    result = run(tmp_path, fetcher, urls=IMG_URLS)
    assert fetcher.requests == IMG_URLS
    assert result.partial == [] and result.downloaded == 2
    for url in IMG_URLS:
        entry = load_progress(tmp_path)["articles"][url]
        assert entry["status"] == "done" and "failed_images" not in entry
        md = md_of(tmp_path, url).read_text(encoding="utf-8")
        assert "](https://" not in md

    fetcher = ImageFetcher({})
    assert run(tmp_path, fetcher, urls=IMG_URLS).skipped == 2 and fetcher.requests == []


def test_still_failing_images_stay_partial_and_good_images_are_kept(tmp_path):
    run(tmp_path, ImageFetcher(image_pages(), broken={IMG_B}), urls=IMG_URLS[:1])
    for attempt in (2, 3):
        fetcher = ImageFetcher(image_pages(), broken={IMG_A, IMG_B})
        result = run(tmp_path, fetcher, urls=IMG_URLS[:1])
        assert fetcher.requests == IMG_URLS[:1]
        entry = load_progress(tmp_path)["articles"][IMG_URLS[0]]
        assert entry["status"] == "partial" and entry["failed_images"] == [IMG_B]
        assert entry["attempts"] == attempt
        assert result.partial[0][2] == [IMG_B]
    md_path = md_of(tmp_path, IMG_URLS[0])
    md = md_path.read_text(encoding="utf-8")
    assert IMG_A not in md and IMG_B in md
    local = list(md_path.with_suffix(".assets").iterdir())
    assert len(local) == 1 and local[0].read_bytes() == b"img:" + IMG_A.encode()


def test_partial_long_link_not_skipped_by_file_id_without_progress(tmp_path):
    run(tmp_path, ImageFetcher(image_pages(), broken={IMG_B}), urls=IMG_URLS[:1])
    (tmp_path / PROGRESS_FILE).unlink()
    fetcher = ImageFetcher(image_pages())
    result = run(tmp_path, fetcher, urls=IMG_URLS[:1])
    assert fetcher.requests == IMG_URLS[:1] and result.skipped == 0
    assert load_progress(tmp_path)["articles"][IMG_URLS[0]]["status"] == "done"


def test_complete_long_link_still_skipped_by_file_id(tmp_path):
    run(tmp_path, ImageFetcher(image_pages()), urls=IMG_URLS[:1])
    (tmp_path / PROGRESS_FILE).unlink()
    fetcher = ImageFetcher({})
    assert run(tmp_path, fetcher, urls=IMG_URLS[:1]).skipped == 1 and fetcher.requests == []


def test_retry_images_off_skips_partial_but_reports_it(tmp_path):
    run(tmp_path, ImageFetcher(image_pages(), broken={IMG_B}), urls=IMG_URLS)
    (tmp_path / PROGRESS_FILE).unlink()
    run(tmp_path, ImageFetcher({}), urls=IMG_URLS[:1], retry_images=False)
    assert load_progress(tmp_path)["articles"][IMG_URLS[0]]["status"] == "partial"
    run(tmp_path, ImageFetcher(image_pages(), broken={IMG_B}), urls=IMG_URLS[1:])
    fetcher = ImageFetcher({})
    result = run(tmp_path, fetcher, urls=IMG_URLS, retry_images=False)
    assert fetcher.requests == [] and result.skipped == 2
    assert [(u, m) for u, _, m in result.partial] == [(IMG_URLS[0], [IMG_B]), (IMG_URLS[1], [IMG_B])]


def test_cli_summary_lists_partial_and_flag_disables_retry(tmp_path, monkeypatch, capsys):
    links = tmp_path / "links.txt"
    links.write_text("\n".join(IMG_URLS), encoding="utf-8")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(batch_module.time, "sleep", lambda s: None)
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: ImageFetcher(image_pages(), broken={IMG_B}))
    assert cli.main(["--urls", str(links), "-o", str(out_dir)]) == 1
    out = capsys.readouterr().out
    assert "缺图 2 篇" in out
    assert "缺 1 张" in out.split("缺图的文章")[1]

    fetcher = ImageFetcher({})
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main(["--urls", str(links), "-o", str(out_dir), "--no-retry-images"]) == 1
    assert fetcher.requests == [] and "未重试" in capsys.readouterr().out

    fetcher = ImageFetcher(image_pages())
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main(["--urls", str(links), "-o", str(out_dir)]) == 0
    assert fetcher.requests == IMG_URLS
    assert "缺图 0 篇" in capsys.readouterr().out


# ---- --no-images 下载的文章：之后启用图片下载时重新处理 ----

def test_no_images_then_default_run_downloads_images(tmp_path):
    fetcher = ImageFetcher(image_pages())
    result = run(tmp_path, fetcher, urls=IMG_URLS, download_images=False)
    assert result.downloaded == 2 and fetcher.image_requests == []
    for url in IMG_URLS:
        entry = load_progress(tmp_path)["articles"][url]
        assert entry["status"] == "done" and entry["images_skipped"] is True

    fetcher = ImageFetcher({})
    assert run(tmp_path, fetcher, urls=IMG_URLS, download_images=False).skipped == 2
    assert fetcher.requests == [] and fetcher.image_requests == []

    fetcher = ImageFetcher(image_pages())
    result = run(tmp_path, fetcher, urls=IMG_URLS)
    assert fetcher.requests == IMG_URLS and result.skipped == 0
    assert fetcher.image_requests == [IMG_A, IMG_B, IMG_A, IMG_B]
    for url in IMG_URLS:
        entry = load_progress(tmp_path)["articles"][url]
        assert entry["status"] == "done" and entry["images_skipped"] is False
        assert "](https://" not in md_of(tmp_path, url).read_text(encoding="utf-8")

    fetcher = ImageFetcher({})
    assert run(tmp_path, fetcher, urls=IMG_URLS).skipped == 2 and fetcher.requests == []


def test_no_images_article_without_images_is_complete(tmp_path):
    run(tmp_path, MapFetcher(pages()), urls=URLS[:1], download_images=False)
    assert load_progress(tmp_path)["articles"][URLS[0]]["images_skipped"] is False
    fetcher = MapFetcher({})
    assert run(tmp_path, fetcher, urls=URLS[:1]).skipped == 1 and fetcher.requests == []


def test_no_images_file_without_progress_is_reprocessed_when_images_enabled(tmp_path):
    run(tmp_path, ImageFetcher(image_pages()), urls=IMG_URLS[:1], download_images=False)
    (tmp_path / PROGRESS_FILE).unlink()
    fetcher = ImageFetcher({})
    assert run(tmp_path, fetcher, urls=IMG_URLS[:1], download_images=False).skipped == 1
    assert load_progress(tmp_path)["articles"][IMG_URLS[0]]["images_skipped"] is True
    (tmp_path / PROGRESS_FILE).unlink()
    fetcher = ImageFetcher(image_pages())
    run(tmp_path, fetcher, urls=IMG_URLS[:1])
    assert fetcher.image_requests == [IMG_A, IMG_B]
    assert load_progress(tmp_path)["articles"][IMG_URLS[0]]["status"] == "done"


@pytest.mark.parametrize("download_images_first, expect_refetch", [(False, True), (True, False)])
def test_legacy_progress_without_flag(tmp_path, download_images_first, expect_refetch):
    run(tmp_path, ImageFetcher(image_pages()), urls=IMG_URLS[1:], download_images=download_images_first)
    data = load_progress(tmp_path)
    for entry in data["articles"].values():
        del entry["images_skipped"]
    (tmp_path / PROGRESS_FILE).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    fetcher = ImageFetcher(image_pages())
    run(tmp_path, fetcher, urls=IMG_URLS[1:])
    assert (fetcher.requests == IMG_URLS[1:]) is expect_refetch
    assert load_progress(tmp_path)["articles"][IMG_URLS[1]]["status"] == "done"


def test_cli_no_images_then_default_run(tmp_path, monkeypatch):
    links = tmp_path / "links.txt"
    links.write_text("\n".join(IMG_URLS), encoding="utf-8")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(batch_module.time, "sleep", lambda s: None)
    first = ImageFetcher(image_pages())
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: first)
    assert cli.main(["--urls", str(links), "-o", str(out_dir), "--no-images"]) == 0
    assert first.image_requests == []
    second = ImageFetcher(image_pages())
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: second)
    assert cli.main(["--urls", str(links), "-o", str(out_dir)]) == 0
    assert len(second.image_requests) == 4
    assert {e["status"] for e in load_progress(out_dir)["articles"].values()} == {"done"}
