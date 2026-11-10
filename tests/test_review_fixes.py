"""
针对 main（b322696）代码审查各条问题的回归测试，测试名里的编号对应审查条目。
"""
from pathlib import Path

import pytest
import yaml

import wechat_downloader.downloader as downloader_module
from wechat_downloader import main as cli
from wechat_downloader.api import WeChatAPI
from wechat_downloader.downloader import ArticleDownloader, article_id
from wechat_downloader.fetch import VerificationRequired, WeChatError, check_article_page
from wechat_downloader.parse import ParseError, extract_js_var, parse_article
from wechat_downloader.render import render_markdown

from test_article import split_front_matter

FIXTURES = Path(__file__).parent / "fixtures"
SHORT_URL = "https://mp.weixin.qq.com/s/AbCdEf123"


def make_page(content: str, title: str = "测试", biz: str = "MzI4NjAxNjY4Nw==",
              msg_link: str = "", author: str = "作者", nickname: str = "测试号") -> str:
    return f"""<html><script>
var biz = "{biz}";
var nickname = htmlDecode("{nickname}");
var msg_title = '{title}'.html(false);
var author = "{author}";
var create_time = "1733136173" * 1;
var msg_link = "{msg_link}";
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


def test_1_short_link_article_list_simple_uses_page_biz(monkeypatch):
    api = WeChatAPI()
    api.fetcher = FakeFetcher(make_page("<p>正文</p>"))
    requested = []

    class Response:
        text = ""

        def raise_for_status(self):
            pass

    monkeypatch.setattr(api.session, "get", lambda url, **kw: requested.append(url) or Response())
    api.get_article_list_simple(SHORT_URL)
    assert requested and "__biz=MzI4NjAxNjY4Nw==" in requested[0]


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
    assert "![前置说明](2024-12-02_测试_52a063f7.assets/001.jpg)" in md
    assert "![](2024-12-02_测试_52a063f7.assets/002.jpg)" in md
    assert "![后置说明](2024-12-02_测试_52a063f7.assets/003.jpg)" in md


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
        image = path.with_name(path.stem + ".assets") / "001.jpg"
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
