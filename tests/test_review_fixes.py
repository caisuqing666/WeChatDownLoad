"""
针对 main（b322696）代码审查各条问题的回归测试，测试名里的编号对应审查条目。
"""
from pathlib import Path

import hashlib
import os
import re
import signal
import threading

import pytest
import yaml

import wechat_downloader.downloader as downloader_module
from wechat_downloader import main as cli
from wechat_downloader.api import WeChatAPI
from wechat_downloader.downloader import ArticleDownloader, RollbackError, _defer_sigint, article_id
from wechat_downloader.fetch import VerificationRequired, WeChatError, check_article_page
from wechat_downloader.parse import ParseError, extract_js_var, parse_article
from wechat_downloader.render import render_markdown

from test_article import image_name, split_front_matter

FIXTURES = Path(__file__).parent / "fixtures"
SHORT_URL = "https://mp.weixin.qq.com/s/AbCdEf123"


def make_page(content: str, title: str = "测试", biz: str = "MzI4NjAxNjY4Nw==",
              msg_link: str = "", author: str = "作者", nickname: str = "测试号", extra_js: str = "") -> str:
    return f"""<html><script>
var biz = "{biz}";
var nickname = htmlDecode("{nickname}");
var msg_title = '{title}'.html(false);
var author = "{author}";
var create_time = "1733136173" * 1;
var msg_link = "{msg_link}";
{extra_js}
</script><div id="js_content">{content}</div></html>"""


class FakeFetcher:
    def __init__(self, page, broken_images=()):
        self.page = page
        self.broken_images = set(broken_images)
        self.image_requests = []

    def get_article_html(self, url):
        check_article_page(self.page)
        return self.page

    def get_image(self, url):
        self.image_requests.append(url)
        if url in self.broken_images:
            raise WeChatError("下载图片失败：404")
        return b"img:" + url.encode(), "image/jpeg"


# 1) 短链接不带 __biz，不能在请求前就失败

def test_1_short_link_account_info_reads_biz_from_page():
    api = WeChatAPI()
    api.fetcher = FakeFetcher(make_page("<p>正文</p>"))
    info = api.get_account_info(SHORT_URL)
    assert info["biz_id"] == "MzI4NjAxNjY4Nw=="
    assert info["account_name"] == "测试号"


# 2) 图片：无 alt、alt 在 src 前面都要正确

IMAGES_HTML = (
    '<p><img alt="前置说明" data-src="https://mmbiz.qpic.cn/a/640?wx_fmt=png"></p>'
    '<p><img data-src="https://mmbiz.qpic.cn/b/640?wx_fmt=jpeg"></p>'
    '<p><img src="https://mmbiz.qpic.cn/c/640" alt="后置说明"></p>'
)


def test_2_image_alt_order_and_missing_alt_remote():
    md = render_markdown(parse_article(make_page(IMAGES_HTML), SHORT_URL))
    assert "![前置说明](https://mmbiz.qpic.cn/a/640?wx_fmt=png)" in md
    assert "![](https://mmbiz.qpic.cn/b/640?wx_fmt=jpeg)" in md
    assert "![后置说明](https://mmbiz.qpic.cn/c/640)" in md


def test_2_image_alt_order_and_missing_alt_local(tmp_path):
    downloader = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(make_page(IMAGES_HTML)))
    md = downloader.download(SHORT_URL).path.read_text(encoding="utf-8")
    assets = "2024-12-02_测试_52a063f7.assets"
    assert f"![前置说明]({assets}/{image_name(1, 'https://mmbiz.qpic.cn/a/640?wx_fmt=png', '.jpg')})" in md
    assert f"![]({assets}/{image_name(2, 'https://mmbiz.qpic.cn/b/640?wx_fmt=jpeg', '.jpg')})" in md
    assert f"![后置说明]({assets}/{image_name(3, 'https://mmbiz.qpic.cn/c/640', '.jpg')})" in md


# 3) 验证页、空正文不能写出“成功”的文件

def test_3_verification_page_returns_none_and_writes_nothing(tmp_path):
    page = (FIXTURES / "real" / "verify.html").read_text(encoding="utf-8")
    api = WeChatAPI()
    api.fetcher = FakeFetcher(page)
    assert api.get_article_content(SHORT_URL) is None
    with pytest.raises(VerificationRequired):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(page)).download(SHORT_URL)
    assert list(tmp_path.iterdir()) == []


def test_3_blank_content_writes_nothing(tmp_path):
    page = make_page("<section> <p>&nbsp;</p> </section>")
    with pytest.raises(ParseError):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(page)).download(SHORT_URL)
    assert list(tmp_path.iterdir()) == []


def test_3_legacy_download_article_rejects_empty_content(tmp_path):
    downloader = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(""))
    with pytest.raises(ParseError):
        downloader.download_article({"title": "空", "content": "", "images": []}, account_name="号")
    assert list(tmp_path.iterdir()) == []


# 5) 默认下载全部图片（不止 20 张），失败要明确报告

MANY = [f"https://mmbiz.qpic.cn/img{i}/640?wx_fmt=png" for i in range(25)]
MANY_HTML = "".join(f'<p><img data-src="{url}"></p>' for url in MANY)


def test_5_all_images_downloaded_by_default(tmp_path):
    fetcher = FakeFetcher(make_page(MANY_HTML))
    result = ArticleDownloader(output_dir=str(tmp_path), fetcher=fetcher).download(SHORT_URL)
    assert fetcher.image_requests == MANY
    assert len(list(result.path.with_name(result.path.stem + ".assets").iterdir())) == 25
    assert "mmbiz.qpic.cn" not in split_front_matter(result.path.read_text(encoding="utf-8"))[1]


def test_5_legacy_download_article_downloads_images_by_default(tmp_path):
    fetcher = FakeFetcher("")
    downloader = ArticleDownloader(output_dir=str(tmp_path), fetcher=fetcher)
    article = parse_article(make_page(MANY_HTML), SHORT_URL)
    downloader.download_article(article.to_dict(), account_name="号")
    assert fetcher.image_requests == MANY


def test_5_cli_downloads_images_and_reports_failures(tmp_path, monkeypatch, capsys):
    broken = MANY[21]
    fetcher = FakeFetcher(make_page(MANY_HTML), broken_images=[broken])
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main([SHORT_URL, "-o", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "1 张图片下载失败" in out
    assert broken in out
    assert len(fetcher.image_requests) == 25


# 6) 正文里含 const / window. 的行、超长行不能被删

def test_6_js_like_and_long_lines_are_kept():
    long_line = "很长的一段。" * 120
    content = (
        "<p>const 是 JavaScript 的关键字，window.location 可以读取地址。</p>"
        f"<p>{long_line}</p>"
        "<pre><code>var a = 1;</code><code>window.alert(a);</code></pre>"
    )
    md = render_markdown(parse_article(make_page(content), SHORT_URL))
    assert "const 是 JavaScript 的关键字，window.location 可以读取地址。" in md
    assert long_line in md
    assert "```\nvar a = 1;\nwindow.alert(a);\n```" in md


# 7) front matter 用 YAML 序列化，特殊字符能原样读回

@pytest.mark.parametrize("title", [
    "标题: 带冒号",
    "key: value # 不是注释",
    "\"双引号\" 与 'single'",
    "- 像列表项",
    "--- 像分隔线 ---",
    "yes",
    "123",
])
def test_7_front_matter_round_trips_with_safe_load(title):
    article = parse_article(make_page("<p>正文</p>"), SHORT_URL)
    article.title = title
    article.description = "第一行\n第二行: 还有冒号"
    meta, _ = split_front_matter(render_markdown(article))
    assert meta["title"] == title
    assert meta["description"] == "第一行\n第二行: 还有冒号"
    assert meta["author"] == "作者"
    assert meta["date"] == "2024-12-02T18:42:53+08:00"


def test_7_front_matter_is_single_yaml_document():
    article = parse_article(make_page("<p>正文</p>", title="a: b"), SHORT_URL)
    md = render_markdown(article)
    head = md[4:md.index("\n---\n", 4)]
    assert isinstance(yaml.safe_load(head), dict)


# ---- PR #2 复核 ----

def long_link(mid: int, idx: int = 1) -> str:
    return f"http://mp.weixin.qq.com/s?__biz=MzI4NjAxNjY4Nw==\\x26amp;mid={mid}\\x26amp;idx={idx}\\x26amp;sn=s{mid}#rd"


def tree(root: Path):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


# P1) 同号同日同标题的不同文章不能互相覆盖；同一篇重复下载要幂等

def test_p1_same_title_different_articles_do_not_collide(tmp_path):
    results = []
    for mid in (100, 200):
        page = make_page(f'<p>第 {mid} 篇</p><p><img data-src="https://mmbiz.qpic.cn/{mid}/640"></p>',
                         msg_link=long_link(mid))
        downloader = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(page))
        results.append(downloader.download(f"https://mp.weixin.qq.com/s/link{mid}"))
    first, second = (r.path for r in results)
    assert first != second and first.parent == second.parent
    assert "第 100 篇" in first.read_text(encoding="utf-8")
    assert "第 200 篇" in second.read_text(encoding="utf-8")
    for path, mid in ((first, 100), (second, 200)):
        image = path.with_name(path.stem + ".assets") / image_name(1, f"https://mmbiz.qpic.cn/{mid}/640", ".jpg")
        assert image.read_bytes() == f"img:https://mmbiz.qpic.cn/{mid}/640".encode()


def test_p1_truncated_titles_do_not_collide(tmp_path):
    paths = []
    for mid, suffix in ((1, "甲"), (2, "乙")):
        page = make_page("<p>正文</p>", title="很长的标题" * 30 + suffix, msg_link=long_link(mid))
        paths.append(ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(page)).download(SHORT_URL).path)
    assert paths[0] != paths[1]
    assert len(list(paths[0].parent.glob("*.md"))) == 2
    assert all(len(p.with_suffix(".assets").name.encode("utf-8")) <= 255 for p in paths)


def test_p1_redownload_is_idempotent(tmp_path):
    page = make_page(IMAGES_HTML, msg_link=long_link(300))
    downloader = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(page))
    first = downloader.download(SHORT_URL)
    snapshot = tree(tmp_path)
    again = downloader.download("https://mp.weixin.qq.com/s?__biz=MzI4NjAxNjY4Nw==&mid=300&idx=1&sn=s300")
    assert again.path == first.path
    assert tree(tmp_path) == snapshot
    assert len(list(first.path.parent.glob("*.md"))) == 1


def test_p1_article_id_is_stable_and_distinguishes_idx():
    def make(link):
        return parse_article(make_page("<p>正文</p>", msg_link=link), SHORT_URL)

    assert article_id(make(long_link(1))) == article_id(make(long_link(1)))
    assert article_id(make(long_link(1, idx=1))) != article_id(make(long_link(1, idx=2)))
    no_link = parse_article(make_page("<p>正文</p>"), "https://mp.weixin.qq.com/s/AbCdEf123")
    assert article_id(no_link) == article_id(parse_article(make_page("<p>正文</p>"), "https://mp.weixin.qq.com/s/AbCdEf123/"))
    assert len(article_id(no_link)) == 8


# P2) 代码块里的 <br> 是换行

def test_p2_br_inside_single_code_becomes_newlines():
    content = "<pre><code>line1<br>line2<br/>line3<br>    indented</code></pre>"
    md = render_markdown(parse_article(make_page(content), SHORT_URL))
    assert "```\nline1\nline2\nline3\n    indented\n```" in md


def test_p2_br_inside_pre_without_code():
    md = render_markdown(parse_article(make_page("<pre>a<br>b</pre>"), SHORT_URL))
    assert "```\na\nb\n```" in md


def test_p2_wechat_line_codes_keep_blank_lines():
    content = "<pre><code>a = 1</code><code><br></code><code>b = 2<br></code></pre>"
    md = render_markdown(parse_article(make_page(content), SHORT_URL))
    assert "```\na = 1\n\nb = 2\n```" in md


# P3) JS 转义的 emoji（UTF-16 代理对）要正确合并，孤立代理不能导致崩溃

def test_p3_surrogate_pair_is_joined():
    page = r'<script>var msg_title = "Hi \uD83D\uDE00 \ud83d\udc4d";</script>'
    assert extract_js_var(page, "msg_title") == "Hi 😀 👍"


def test_p3_lone_surrogate_is_replaced():
    page = r'<script>var a = "x\uD83Dy"; var b = "\uDE00";</script>'
    assert extract_js_var(page, "a") == "x\ufffdy"
    assert extract_js_var(page, "b") == "\ufffd"


def test_p3_emoji_metadata_round_trips_through_file(tmp_path):
    page = make_page(
        "<p>正文</p>",
        title=r"表情 \uD83D\uDE00: 测试",
        author=r"作者\uD83D",
        nickname=r"号\ud83c\udf89",
        msg_link=long_link(400),
    )
    result = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(page)).download(SHORT_URL)
    meta, body = split_front_matter(result.path.read_text(encoding="utf-8"))
    assert meta["title"] == "表情 😀: 测试"
    assert meta["author"] == "作者\ufffd"
    assert meta["account"] == "号🎉"
    assert "# 表情 😀: 测试" in body
    assert result.path.parent.name == "号🎉"


# ---- PR #2 第二轮复核 ----

def snapshot(root: Path):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def body_of(path: Path) -> str:
    return split_front_matter(path.read_text(encoding="utf-8"))[1]


def no_temp_files(root: Path) -> bool:
    return not [p for p in root.rglob("*") if p.name.startswith(".")]


class InterruptingFetcher(FakeFetcher):
    def __init__(self, page, fail_at: int):
        super().__init__(page)
        self.fail_at = fail_at

    def get_image(self, url):
        if len(self.image_requests) + 1 == self.fail_at:
            raise KeyboardInterrupt
        return super().get_image(url)


REDOWNLOAD_PAGE = make_page(IMAGES_HTML, msg_link=long_link(500))
IMAGE_B = "https://mmbiz.qpic.cn/b/640?wx_fmt=jpeg"


# R1) 重下失败不能破坏上次成功的结果

def test_r1_failed_image_on_redownload_keeps_previous_local_copy(tmp_path):
    first = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    before = snapshot(first.path.with_suffix(".assets"))
    again = ArticleDownloader(
        output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE, broken_images=[IMAGE_B])
    ).download(SHORT_URL)
    assert again.path == first.path
    assert again.failed_images == []
    assert again.kept_images == [IMAGE_B]
    assert snapshot(first.path.with_suffix(".assets")) == before
    assert IMAGE_B not in body_of(again.path)
    assert no_temp_files(tmp_path)


def test_r1_cli_reports_kept_images(tmp_path, monkeypatch, capsys):
    ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    fetcher = FakeFetcher(REDOWNLOAD_PAGE, broken_images=[IMAGE_B])
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    assert cli.main([SHORT_URL, "-o", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "沿用了上次下载的本地文件" in out and IMAGE_B in out


@pytest.mark.parametrize("fail_at", [1, 2, 3])
def test_r1_interrupted_redownload_leaves_old_result_intact(tmp_path, fail_at):
    ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    before = snapshot(tmp_path)
    downloader = ArticleDownloader(output_dir=str(tmp_path), fetcher=InterruptingFetcher(REDOWNLOAD_PAGE, fail_at))
    with pytest.raises(KeyboardInterrupt):
        downloader.download(SHORT_URL)
    assert snapshot(tmp_path) == before
    assert no_temp_files(tmp_path)


def test_r1_failure_while_writing_markdown_leaves_old_result_intact(tmp_path, monkeypatch):
    ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    before = snapshot(tmp_path)

    def broken_render(article):
        raise RuntimeError("磁盘写满")

    monkeypatch.setattr(downloader_module, "render_markdown", broken_render)
    with pytest.raises(RuntimeError):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    assert snapshot(tmp_path) == before
    assert no_temp_files(tmp_path)


def test_r1_interrupted_first_download_leaves_nothing(tmp_path):
    downloader = ArticleDownloader(output_dir=str(tmp_path), fetcher=InterruptingFetcher(REDOWNLOAD_PAGE, 2))
    with pytest.raises(KeyboardInterrupt):
        downloader.download(SHORT_URL)
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []
    assert no_temp_files(tmp_path)


def test_r1_redownload_with_changed_images_drops_stale_files(tmp_path):
    ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    changed = make_page('<p><img data-src="https://mmbiz.qpic.cn/new/640"></p>', msg_link=long_link(500))
    result = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(changed)).download(SHORT_URL)
    assert [p.name for p in result.path.with_suffix(".assets").iterdir()] == [
        image_name(1, "https://mmbiz.qpic.cn/new/640", ".jpg")
    ]


# R2) 文章 ID 优先取页面变量 biz/mid/idx，不受 msg_link 写法影响

PAGE_VARS = 'var mid = "" || "2650239155"; var idx = "2";'
EXPECTED_ID = hashlib.sha1(b"MzI4NjAxNjY4Nw==:2650239155:2").hexdigest()[:8]
LONG_REQUEST = "https://mp.weixin.qq.com/s?__biz=MzI4NjAxNjY4Nw==&mid=2650239155&idx=2&sn=abc&chksm=x"


@pytest.mark.parametrize("msg_link, request_url", [
    ("https://mp.weixin.qq.com/s/ShortCode123", "https://mp.weixin.qq.com/s/ShortCode123"),
    ("http://mp.weixin.qq.com/s?__biz=MzI4NjAxNjY4Nw==\\x26amp;mid=2650239155\\x26amp;idx=2\\x26amp;sn=abc#rd",
     LONG_REQUEST),
    ("https://mp.weixin.qq.com/s?__biz=MzI4NjAxNjY4Nw==&mid=2650239155&idx=2&sn=abc&chksm=other", SHORT_URL),
    ("", "https://mp.weixin.qq.com/s/AnotherCode"),
    ("", LONG_REQUEST),
])
def test_r2_id_from_page_vars_regardless_of_msg_link(msg_link, request_url):
    page = make_page("<p>正文</p>", msg_link=msg_link, extra_js=PAGE_VARS)
    assert article_id(parse_article(page, request_url)) == EXPECTED_ID


def test_r2_falls_back_to_long_url_params_then_short_code():
    without_vars = make_page("<p>正文</p>")
    assert article_id(parse_article(without_vars, LONG_REQUEST)) == EXPECTED_ID
    short = article_id(parse_article(without_vars, "https://mp.weixin.qq.com/s/ShortCode123"))
    assert short == hashlib.sha1(b"ShortCode123").hexdigest()[:8]


def test_r2_mid_falls_back_to_appmsgid():
    page = make_page("<p>正文</p>", extra_js='var appmsgid = "2650239155"; var itemidx = "2";')
    assert article_id(parse_article(page, SHORT_URL)) == EXPECTED_ID


@pytest.mark.parametrize("name, mid", [
    ("ruanyifeng-ai-workflow", "2650239155"),
    ("python-wechat-backend", "2653552297"),
    ("weixin-reputation-guide", "548251452"),
])
def test_r2_real_pages_id_stable_when_msg_link_changes(name, mid):
    page = (FIXTURES / "real" / f"{name}.html").read_text(encoding="utf-8")
    original = parse_article(page, SHORT_URL)
    assert original.mid == mid and original.idx == "1"
    stripped = re.sub(r"var msg_link = [^;]*;", 'var msg_link = "";', page)
    expected = hashlib.sha1(f"{original.biz}:{mid}:1".encode()).hexdigest()[:8]
    assert article_id(original) == expected
    assert article_id(parse_article(stripped, "https://mp.weixin.qq.com/s/xyz")) == expected


# ---- PR #2 第三轮复核 ----

REAL_REPLACE = os.replace


def fail_replace_when(monkeypatch, predicate, exc=PermissionError("拒绝访问")):
    """让满足条件的 os.replace 调用抛错，其余照常执行"""
    def fake(src, dst):
        if predicate(Path(src), Path(dst)):
            raise exc
        return REAL_REPLACE(src, dst)

    monkeypatch.setattr(downloader_module.os, "replace", fake)


def is_md_commit(src: Path, dst: Path) -> bool:
    return dst.suffix == ".md"


class ChangedBytesFetcher(FakeFetcher):
    def get_image(self, url):
        data, content_type = super().get_image(url)
        return b"v2:" + data, content_type


CHANGED_URLS_PAGE = make_page(
    '<p><img data-src="https://mmbiz.qpic.cn/x/640"></p><p><img data-src="https://mmbiz.qpic.cn/y/640"></p>',
    msg_link=long_link(500),
)


@pytest.mark.parametrize("second_fetcher", [
    pytest.param(lambda: FakeFetcher(REDOWNLOAD_PAGE), id="same-images"),
    pytest.param(lambda: ChangedBytesFetcher(REDOWNLOAD_PAGE), id="same-urls-new-bytes"),
    pytest.param(lambda: FakeFetcher(CHANGED_URLS_PAGE), id="changed-urls"),
    pytest.param(lambda: FakeFetcher(REDOWNLOAD_PAGE, broken_images=[IMAGE_B]), id="one-image-kept"),
])
def test_s1_md_replace_failure_rolls_back_assets(tmp_path, monkeypatch, second_fetcher):
    ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    before = snapshot(tmp_path)
    fail_replace_when(monkeypatch, is_md_commit)
    with pytest.raises(PermissionError):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=second_fetcher()).download(SHORT_URL)
    assert snapshot(tmp_path) == before
    assert no_temp_files(tmp_path)


def test_s1_md_replace_failure_on_first_download_leaves_nothing(tmp_path, monkeypatch):
    fail_replace_when(monkeypatch, is_md_commit)
    with pytest.raises(PermissionError):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []
    assert no_temp_files(tmp_path)


def test_s1_installing_new_assets_failure_restores_backup(tmp_path, monkeypatch):
    ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    before = snapshot(tmp_path)
    fail_replace_when(monkeypatch, lambda src, dst: dst.suffix == ".assets" and ".old." not in str(src))
    with pytest.raises(PermissionError):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=ChangedBytesFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    assert snapshot(tmp_path) == before
    assert no_temp_files(tmp_path)


def test_s1_rollback_failure_is_reported_and_keeps_backup(tmp_path, monkeypatch):
    first = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    old_md = first.path.read_bytes()
    old_assets = snapshot(first.path.with_suffix(".assets"))
    fail_replace_when(
        monkeypatch,
        lambda src, dst: is_md_commit(src, dst) or (".old." in str(src) and dst.suffix == ".assets"),
    )
    with pytest.raises(RollbackError) as info:
        ArticleDownloader(output_dir=str(tmp_path), fetcher=ChangedBytesFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    backups = [p for p in first.path.parent.iterdir() if ".old." in p.name]
    assert len(backups) == 1
    kept = backups[0] / first.path.with_suffix(".assets").name
    assert str(kept) in str(info.value)
    assert snapshot(kept) == old_assets
    assert first.path.read_bytes() == old_md


def test_s1_successful_redownload_removes_backup(tmp_path):
    ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    result = ArticleDownloader(output_dir=str(tmp_path), fetcher=ChangedBytesFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    assert all(data.startswith(b"v2:") for data in snapshot(result.path.with_suffix(".assets")).values())
    assert no_temp_files(tmp_path)


# S2) biz / mid / idx 逐字段回退：页面变量 -> 链接参数 -> idx 默认 1

def page_with(js: str) -> str:
    return make_page("<p>正文</p>", biz="", extra_js=js)


def link(biz="MzI4NjAxNjY4Nw==", mid="2650239155", idx=None):
    url = f"https://mp.weixin.qq.com/s?__biz={biz}&mid={mid}&sn=abc"
    return url + (f"&idx={idx}" if idx else "")


def expected_id(idx="1", biz="MzI4NjAxNjY4Nw==", mid="2650239155"):
    return hashlib.sha1(f"{biz}:{mid}:{idx}".encode()).hexdigest()[:8]


FULL_VARS = 'var biz = "MzI4NjAxNjY4Nw=="; var mid = "2650239155";'


def test_s2_missing_page_idx_uses_link_idx():
    page = page_with(FULL_VARS)
    first = article_id(parse_article(page, link(idx="1")))
    second = article_id(parse_article(page, link(idx="2")))
    assert first != second
    assert first == expected_id("1") and second == expected_id("2")


def test_s2_idx_defaults_to_1_only_when_nowhere():
    assert article_id(parse_article(page_with(FULL_VARS), link())) == expected_id("1")
    assert article_id(parse_article(page_with(FULL_VARS), SHORT_URL)) == expected_id("1")


def test_s2_page_idx_wins_over_link_idx():
    page = page_with(FULL_VARS + ' var idx = "3";')
    assert article_id(parse_article(page, link(idx="2"))) == expected_id("3")


def test_s2_missing_page_mid_uses_link_mid():
    page = page_with('var biz = "MzI4NjAxNjY4Nw=="; var idx = "2";')
    a = article_id(parse_article(page, link(mid="111")))
    b = article_id(parse_article(page, link(mid="222")))
    assert a == expected_id("2", mid="111") and b == expected_id("2", mid="222")


def test_s2_missing_page_biz_uses_link_biz():
    page = page_with('var mid = "2650239155"; var idx = "2";')
    a = article_id(parse_article(page, link(biz="AAA=")))
    b = article_id(parse_article(page, link(biz="BBB=")))
    assert a == expected_id("2", biz="AAA=") and b == expected_id("2", biz="BBB=")


def test_s2_request_url_params_used_when_msg_link_is_short():
    page = make_page("<p>正文</p>", biz="", msg_link="https://mp.weixin.qq.com/s/Short1", extra_js=FULL_VARS)
    assert article_id(parse_article(page, link(idx="2"))) == expected_id("2")


# ---- PR #2 第四轮复核 ----

REAL_RMTREE = downloader_module.shutil.rmtree
NEW_PAGE = make_page(IMAGES_HTML + "<p>第二版</p>", msg_link=long_link(500))


def assert_consistent(root: Path, before: dict):
    """结果只能是完整的旧版本或完整的新版本，并且没有临时文件"""
    assert no_temp_files(root)
    md_files = list(root.rglob("*.md"))
    if not before and not md_files:
        assert [p for p in root.rglob("*") if p.is_file()] == []
        return "nothing"
    (md,) = md_files
    text = md.read_text(encoding="utf-8")
    if "第二版" not in text:
        assert snapshot(root) == before
        return "old"
    assets = md.with_suffix(".assets")
    files = snapshot(assets)
    referenced = sorted(re.findall(r"\.assets/([^)]+)\)", text))
    assert sorted(files) == referenced
    assert all(data.startswith(b"v2:") for data in files.values())
    return "new"


def interrupt_after_nth_replace(monkeypatch, n):
    calls = []

    def fake(src, dst):
        REAL_REPLACE(src, dst)
        calls.append((src, dst))
        if len(calls) == n:
            raise KeyboardInterrupt

    monkeypatch.setattr(downloader_module.os, "replace", fake)


def prepare(tmp_path, existing: bool) -> dict:
    if existing:
        ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    return snapshot(tmp_path)


# 提交区段里的 os.replace 依次是：旧图片目录 -> 备份、新图片目录 -> 正式位置、临时 .md -> 正式 .md；
# 首次下载时没有第一步
@pytest.mark.parametrize("existing, n, expected", [
    (True, 1, "old"),
    (True, 2, "old"),
    (True, 3, "new"),
    (False, 1, "nothing"),
    (False, 2, "new"),
])
def test_t1_interrupt_right_after_each_replace(tmp_path, monkeypatch, existing, n, expected):
    before = prepare(tmp_path, existing)
    interrupt_after_nth_replace(monkeypatch, n)
    with pytest.raises(KeyboardInterrupt):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=ChangedBytesFetcher(NEW_PAGE)).download(SHORT_URL)
    assert assert_consistent(tmp_path, before) == expected


@pytest.mark.parametrize("delete_first", [False, True], ids=["before-delete-backup", "after-delete-backup"])
def test_t1_interrupt_around_backup_deletion(tmp_path, monkeypatch, delete_first):
    before = prepare(tmp_path, True)

    def fake(path, *args, **kwargs):
        if ".old." in Path(path).name and not fake.done:
            fake.done = True
            if delete_first:
                REAL_RMTREE(path, *args, **kwargs)
            raise KeyboardInterrupt
        return REAL_RMTREE(path, *args, **kwargs)

    fake.done = False
    monkeypatch.setattr(downloader_module.shutil, "rmtree", fake)
    with pytest.raises(KeyboardInterrupt):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=ChangedBytesFetcher(NEW_PAGE)).download(SHORT_URL)
    assert fake.done
    assert assert_consistent(tmp_path, before) == "new"


def test_t1_ordinary_error_after_md_replace_keeps_new_result(tmp_path, monkeypatch):
    before = prepare(tmp_path, True)

    def fake(path, *args, **kwargs):
        if ".old." in Path(path).name and not fake.done:
            fake.done = True
            raise OSError("模拟删除备份时出错")
        return REAL_RMTREE(path, *args, **kwargs)

    fake.done = False
    monkeypatch.setattr(downloader_module.shutil, "rmtree", fake)
    with pytest.raises(OSError):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=ChangedBytesFetcher(NEW_PAGE)).download(SHORT_URL)
    assert assert_consistent(tmp_path, before) == "new"


# SIGINT 延迟

def test_t2_sigint_is_deferred_until_section_ends():
    original = signal.getsignal(signal.SIGINT)
    reached_end = False
    with pytest.raises(KeyboardInterrupt):
        with _defer_sigint():
            os.kill(os.getpid(), signal.SIGINT)
            for _ in range(1000):
                pass
            reached_end = True
    assert reached_end
    assert signal.getsignal(signal.SIGINT) is original


def test_t2_no_signal_means_no_exception_and_handler_restored():
    original = signal.getsignal(signal.SIGINT)
    with _defer_sigint():
        assert signal.getsignal(signal.SIGINT) is not original
    assert signal.getsignal(signal.SIGINT) is original


def test_t2_previous_handler_is_called_once(monkeypatch):
    seen = []
    previous = signal.signal(signal.SIGINT, lambda signum, frame: seen.append(signum))
    try:
        with _defer_sigint():
            os.kill(os.getpid(), signal.SIGINT)
            os.kill(os.getpid(), signal.SIGINT)
            assert seen == []
        assert seen == [signal.SIGINT]
    finally:
        signal.signal(signal.SIGINT, previous)


def test_t2_ignored_sigint_stays_ignored():
    previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        with _defer_sigint():
            os.kill(os.getpid(), signal.SIGINT)
        assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN
    finally:
        signal.signal(signal.SIGINT, previous)


def test_t2_worker_thread_does_not_touch_handlers():
    original = signal.getsignal(signal.SIGINT)
    seen = []

    def work():
        with _defer_sigint():
            seen.append(signal.getsignal(signal.SIGINT))

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    assert seen == [original]


def test_t2_real_sigint_during_commit_finishes_commit_first(tmp_path, monkeypatch):
    before = prepare(tmp_path, True)

    def fake(src, dst):
        REAL_REPLACE(src, dst)
        if Path(dst).suffix == ".assets" and ".old." not in str(dst):
            os.kill(os.getpid(), signal.SIGINT)

    monkeypatch.setattr(downloader_module.os, "replace", fake)
    with pytest.raises(KeyboardInterrupt):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=ChangedBytesFetcher(NEW_PAGE)).download(SHORT_URL)
    assert assert_consistent(tmp_path, before) == "new"


# ---- PR #2 第五轮复核 ----

def sigint_then(exc):
    """返回一个先给自己发 SIGINT 再抛 exc 的动作，模拟“提交时按了 Ctrl+C 又碰上写入失败”"""
    def act():
        os.kill(os.getpid(), signal.SIGINT)
        raise exc
    return act


def patch_commit(monkeypatch, on_md, on_restore=None):
    def fake(src, dst):
        src, dst = Path(src), Path(dst)
        if dst.suffix == ".md":
            on_md()
        if on_restore is not None and ".old." in str(src) and dst.suffix == ".assets":
            on_restore()
        return REAL_REPLACE(src, dst)

    monkeypatch.setattr(downloader_module.os, "replace", fake)


def raise_(exc):
    def act():
        raise exc
    return act


def test_u1_rollback_error_is_outermost_despite_sigint(tmp_path, monkeypatch):
    first = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(REDOWNLOAD_PAGE)).download(SHORT_URL)
    old_md = first.path.read_bytes()
    old_assets = snapshot(first.path.with_suffix(".assets"))
    original = signal.getsignal(signal.SIGINT)
    patch_commit(monkeypatch, sigint_then(PermissionError("拒绝访问")), raise_(OSError("恢复失败")))
    with pytest.raises(RollbackError) as info:
        ArticleDownloader(output_dir=str(tmp_path), fetcher=ChangedBytesFetcher(NEW_PAGE)).download(SHORT_URL)
    error = info.value
    assert error.interrupted is True
    assert "收到过中断" in str(error)
    assert error.backup_path is not None and error.backup_path.is_dir()
    assert snapshot(error.backup_path) == old_assets
    assert first.path.read_bytes() == old_md
    assert signal.getsignal(signal.SIGINT) is original


def test_u1_rollback_error_without_sigint_is_not_marked(tmp_path, monkeypatch):
    prepare(tmp_path, True)
    patch_commit(monkeypatch, raise_(PermissionError("拒绝访问")), raise_(OSError("恢复失败")))
    with pytest.raises(RollbackError) as info:
        ArticleDownloader(output_dir=str(tmp_path), fetcher=ChangedBytesFetcher(NEW_PAGE)).download(SHORT_URL)
    assert info.value.interrupted is False
    assert "收到过中断" not in str(info.value)


def test_u2_sigint_with_recovered_failure_raises_original_error(tmp_path, monkeypatch):
    """
    提交失败但回滚成功时，抛出的是原来的提交错误（这里是 PermissionError），而不是 KeyboardInterrupt：
    区段内已有异常在传播时一律不补发中断，只在异常上标记 interrupted=True；
    磁盘已恢复成旧版本，CLI 看到这个标记会以 130 退出。
    """
    before = prepare(tmp_path, True)
    original = signal.getsignal(signal.SIGINT)
    patch_commit(monkeypatch, sigint_then(PermissionError("拒绝访问")))
    with pytest.raises(PermissionError) as info:
        ArticleDownloader(output_dir=str(tmp_path), fetcher=ChangedBytesFetcher(NEW_PAGE)).download(SHORT_URL)
    assert getattr(info.value, "interrupted", False) is True
    assert assert_consistent(tmp_path, before) == "old"
    assert signal.getsignal(signal.SIGINT) is original


def test_u2_defer_sigint_does_not_mask_inflight_exception():
    seen = []
    previous = signal.signal(signal.SIGINT, lambda signum, frame: seen.append(signum))
    try:
        with pytest.raises(ValueError) as info:
            with _defer_sigint():
                os.kill(os.getpid(), signal.SIGINT)
                raise ValueError("区段内的错误")
        assert info.value.interrupted is True
        assert seen == []
    finally:
        signal.signal(signal.SIGINT, previous)


def test_u2_no_inflight_exception_still_raises_keyboard_interrupt():
    with pytest.raises(KeyboardInterrupt):
        with _defer_sigint():
            os.kill(os.getpid(), signal.SIGINT)


def run_cli(tmp_path, monkeypatch, fetcher, urls):
    monkeypatch.setattr(downloader_module, "Fetcher", lambda: fetcher)
    return cli.main([*urls, "-o", str(tmp_path), "--interval", "0"])


def test_u3_cli_rollback_error_with_sigint_exits_130_and_prints_backup(tmp_path, monkeypatch, capsys):
    prepare(tmp_path, True)
    patch_commit(monkeypatch, sigint_then(PermissionError("拒绝访问")), raise_(OSError("恢复失败")))
    fetcher = ChangedBytesFetcher(NEW_PAGE)
    assert run_cli(tmp_path, monkeypatch, fetcher, [SHORT_URL, SHORT_URL]) == 130
    out = capsys.readouterr().out
    backups = [p for p in tmp_path.rglob("*.assets") if ".old." in p.parent.name]
    assert len(backups) == 1 and str(backups[0]) in out
    assert "[2/2]" not in out


def test_u3_cli_rollback_error_without_sigint_exits_1_and_stops(tmp_path, monkeypatch, capsys):
    prepare(tmp_path, True)
    patch_commit(monkeypatch, raise_(PermissionError("拒绝访问")), raise_(OSError("恢复失败")))
    fetcher = ChangedBytesFetcher(NEW_PAGE)
    assert run_cli(tmp_path, monkeypatch, fetcher, [SHORT_URL, SHORT_URL]) == 1
    out = capsys.readouterr().out
    assert "旧图片备份：" in out
    assert "[2/2]" not in out


def test_u3_cli_interrupted_ordinary_failure_exits_130(tmp_path, monkeypatch, capsys):
    prepare(tmp_path, True)
    patch_commit(monkeypatch, sigint_then(PermissionError("拒绝访问")))
    assert run_cli(tmp_path, monkeypatch, ChangedBytesFetcher(NEW_PAGE), [SHORT_URL]) == 130
    assert "期间收到过中断" in capsys.readouterr().out
