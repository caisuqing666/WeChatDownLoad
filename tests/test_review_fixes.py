"""
针对 main（b322696）代码审查各条问题的回归测试，测试名里的编号对应审查条目。
"""
from pathlib import Path

import pytest
import yaml

import wechat_downloader.downloader as downloader_module
from wechat_downloader import main as cli
from wechat_downloader.api import WeChatAPI
from wechat_downloader.downloader import ArticleDownloader
from wechat_downloader.fetch import VerificationRequired, WeChatError, check_article_page
from wechat_downloader.parse import ParseError, parse_article
from wechat_downloader.render import render_markdown

from test_article import split_front_matter

FIXTURES = Path(__file__).parent / "fixtures"
SHORT_URL = "https://mp.weixin.qq.com/s/AbCdEf123"


def make_page(content: str, title: str = "测试", biz: str = "MzI4NjAxNjY4Nw==") -> str:
    return f"""<html><script>
var biz = "{biz}";
var nickname = htmlDecode("测试号");
var msg_title = '{title}'.html(false);
var author = "作者";
var create_time = "1733136173" * 1;
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
    assert "![前置说明](2024-12-02_测试.assets/001.jpg)" in md
    assert "![](2024-12-02_测试.assets/002.jpg)" in md
    assert "![后置说明](2024-12-02_测试.assets/003.jpg)" in md


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
