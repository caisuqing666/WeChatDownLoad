from pathlib import Path

import pytest

from wechat_downloader.downloader import ArticleDownloader, safe_filename
from wechat_downloader.fetch import (
    ArticleUnavailable,
    VerificationRequired,
    check_article_page,
    normalize_url,
)
from wechat_downloader.parse import ParseError, extract_js_var, parse_article
from wechat_downloader.render import render_markdown

FIXTURES = Path(__file__).parent / "fixtures"
SHORT_URL = "https://mp.weixin.qq.com/s/AbCdEf123"


@pytest.fixture
def page():
    return (FIXTURES / "article.html").read_text(encoding="utf-8")


@pytest.fixture
def article(page):
    return parse_article(page, SHORT_URL)


class FakeFetcher:
    def __init__(self, page):
        self.page = page

    def get_article_html(self, url):
        check_article_page(self.page)
        return self.page


def test_js_var_takes_first_non_empty_literal(page):
    assert extract_js_var(page, "biz") == "MzI4NjAxNjY4Nw=="


def test_js_var_decodes_escapes_and_entities(page):
    assert extract_js_var(page, "nickname") == "测试公众号 & 朋友"
    assert extract_js_var(page, "msg_title") == "测试文章：\"引号\" 与 '单引号'"


def test_metadata_comes_from_page_not_short_url(article):
    assert article.biz == "MzI4NjAxNjY4Nw=="
    assert article.account_name == "测试公众号 & 朋友"
    assert article.author == "张三"
    assert article.publish_time.isoformat() == "2024-12-02T18:42:53+08:00"
    assert article.cover == "https://mmbiz.qpic.cn/mmbiz_jpg/cover/0?wx_fmt=jpeg"
    assert article.url == "https://mp.weixin.qq.com/s?__biz=MzI4NjAxNjY4Nw==&mid=1&idx=1&sn=abc"


def test_nested_content_is_not_truncated(article):
    assert "嵌套在 div 里的第二段" in article.content_html
    assert "最后一段" in article.content_html


def test_lazy_images_use_data_src(article):
    assert article.images == [
        "https://mmbiz.qpic.cn/mmbiz_png/abc/640?wx_fmt=png&from=appmsg",
        "https://mmbiz.qpic.cn/mmbiz_jpg/def/640?wx_fmt=jpeg",
    ]
    assert "data:image" not in article.content_html


def test_non_content_blocks_removed(article):
    assert "shouldNotAppear" not in article.content_html
    assert "别的公众号" not in article.content_html
    assert "visibility" not in article.content_html


def test_markdown_output(article):
    md = render_markdown(article)
    assert md.startswith("---\ntitle: \"测试文章：\\\"引号\\\" 与 '单引号'\"\n")
    assert "\n# 测试文章：\"引号\" 与 '单引号'\n" in md
    assert "## 一、引言" in md
    assert "第一段，**加粗**文字。" in md
    assert "![](https://mmbiz.qpic.cn/mmbiz_png/abc/640?wx_fmt=png&from=appmsg)" in md
    assert "![示意图](https://mmbiz.qpic.cn/mmbiz_jpg/def/640?wx_fmt=jpeg)" in md
    assert '```python\ndef hello():\n    return "*not italic*"\n\nprint(hello())\n```' in md
    assert "<" not in md.split("---", 2)[2].replace("<br>", "")


def test_download_writes_markdown_without_image_files(tmp_path, page):
    downloader = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(page))
    result = downloader.download(SHORT_URL)
    assert result.path == tmp_path / "测试公众号 & 朋友" / "2024-12-02_测试文章：_引号_ 与 '单引号'.md"
    assert result.path.read_text(encoding="utf-8").startswith("---\n")
    assert [p.name for p in result.path.parent.iterdir()] == [result.path.name]


def test_verification_page_detected():
    page = (FIXTURES / "verify.html").read_text(encoding="utf-8")
    with pytest.raises(VerificationRequired):
        check_article_page(page)


def test_deleted_article_detected():
    with pytest.raises(ArticleUnavailable):
        check_article_page("<html><body>该内容已被发布者删除</body></html>")


def test_wechat_notice_page_detected():
    page = '<div class="weui-msg"><h2 class="weui-msg__title">参数错误</h2></div>'
    with pytest.raises(ArticleUnavailable, match="参数错误"):
        check_article_page(page)


def test_page_without_content_raises_parse_error():
    with pytest.raises(ParseError):
        parse_article('<html><script>var item_show_type = "8";</script></html>', SHORT_URL)


@pytest.mark.parametrize("raw, expected", [
    ("http://mp.weixin.qq.com/s?__biz=X&amp;mid=1#wechat_redirect", "https://mp.weixin.qq.com/s?__biz=X&mid=1"),
    ("  https://mp.weixin.qq.com/s/abc  ", "https://mp.weixin.qq.com/s/abc"),
    ("mp.weixin.qq.com/s/abc", "https://mp.weixin.qq.com/s/abc"),
])
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ('a/b:c*d?"e"<f>|g', "a_b_c_d__e__f__g"),
    ("  多余   空格. ", "多余 空格"),
    ("CON", "_CON"),
    ("", "未命名"),
])
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected
