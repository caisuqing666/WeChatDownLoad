"""
用真实抓取的文章页面做离线测试。页面由 tests/fixtures/trim_page.py 裁剪过：
只删除了与解析无关的内联 JS/CSS，正文和元数据脚本保持原样。
"""
from pathlib import Path
from urllib.parse import unquote

import pytest
from bs4 import BeautifulSoup

from wechat_downloader.downloader import ArticleDownloader, markdown_path
from wechat_downloader.fetch import ArticleUnavailable, VerificationRequired, check_article_page
from wechat_downloader.parse import parse_article
from wechat_downloader.render import render_markdown

REAL = Path(__file__).parent / "fixtures" / "real"
# 故意不带任何参数，确保元数据只能来自页面变量
BARE_URL = "https://mp.weixin.qq.com/s/fixture"

# 抓取来源：
#   ruanyifeng-ai-workflow   https://mp.weixin.qq.com/s?__biz=MzI4NjAxNjY4Nw==&mid=2650239155&idx=1&sn=0c34134277e7c881d575fe60b46dae33&chksm=...
#   python-wechat-backend    https://mp.weixin.qq.com/s/wjb995FvkXhfCXSmSkFtKw
#   weixin-reputation-guide  https://mp.weixin.qq.com/s/_2kC-fXw7UjneZSrsC9CVQ
#   unknown-error            上面第一篇的长链接去掉 chksm 后的返回页（未裁剪）
#   param-error              不存在的短链接的返回页
#   verify                   连续请求后微信返回的“环境异常”验证页（未裁剪）
ARTICLES = {
    "ruanyifeng-ai-workflow": dict(
        title="AI 应用无代码开发教程：工作流模式详解",
        account_name="阮一峰的网络日志",
        author="阮一峰",
        biz="MzI4NjAxNjY4Nw==",
        user_name="gh_2f5c59ad6e1e",
        date="2024-12-02T18:42:53+08:00",
        images=44,
    ),
    "python-wechat-backend": dict(
        title="Python开发微信公众号后台（系列一）",
        account_name="橙哥出海",
        author="段晓晨",
        biz="MzAxMjUyNDQ5OA==",
        user_name="gh_d8489149b735",
        date="2016-12-05T21:29:18+08:00",
        images=10,
    ),
    "weixin-reputation-guide": dict(
        title="名誉保护投诉指引",
        account_name="微信公众平台",
        author="微信公众平台",
        biz="MjM5NDAwMTA2MA==",
        user_name="weixinguanhaozhushou",
        date="2020-11-27T16:23:54+08:00",
        images=14,
    ),
}


def load(name: str) -> str:
    return (REAL / f"{name}.html").read_text(encoding="utf-8")


class FakeFetcher:
    def __init__(self, page):
        self.page = page

    def get_article_html(self, url):
        check_article_page(self.page)
        return self.page

    def get_image(self, url):
        return b"\x89PNG fake", "image/png"


@pytest.fixture(params=sorted(ARTICLES))
def real(request):
    name = request.param
    page = load(name)
    return page, parse_article(page, BARE_URL), ARTICLES[name]


def test_real_page_passes_checks(real):
    page, _, _ = real
    check_article_page(page)


def test_real_metadata_from_page_variables(real):
    _, article, expected = real
    assert article.title == expected["title"]
    assert article.account_name == expected["account_name"]
    assert article.author == expected["author"]
    assert article.biz == expected["biz"]
    assert article.user_name == expected["user_name"]
    assert article.publish_time.isoformat() == expected["date"]
    assert article.url.startswith("https://mp.weixin.qq.com/s")
    assert article.url != BARE_URL


def test_real_images_come_from_data_src(real):
    page, article, expected = real
    lazy = {
        img["data-src"]
        for img in BeautifulSoup(page, "html.parser").select_one("#js_content").find_all("img")
        if img.get("data-src")
    }
    assert len(article.images) == expected["images"]
    assert all(src.startswith("https://mmbiz.qpic.cn/") for src in article.images)
    assert len(lazy) == len(article.images)
    assert "data:image" not in article.content_html
    assert "data-src" not in article.content_html


def test_real_markdown_is_clean(real):
    _, article, expected = real
    md = render_markdown(article)
    head, body = md.split("---", 2)[1:]
    assert f'title: "{expected["title"]}"' in head
    assert f'date: "{expected["date"]}"' in head
    assert f"\n# {expected['title']}\n" in body
    assert "<section" not in body and "<span" not in body and "<img" not in body
    assert "visibility" not in body


def test_real_code_block_kept_as_fence():
    md = render_markdown(parse_article(load("python-wechat-backend"), BARE_URL))
    assert "```\n# coding: UTF-8\n" in md
    assert "app_root = os.path.dirname(__file__)" in md


def test_real_download_localizes_all_images(tmp_path, real):
    page, _, expected = real
    result = ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(page)).download(BARE_URL)
    assets = result.path.with_name(result.path.stem + ".assets")
    assert len(list(assets.iterdir())) == expected["images"]
    body = result.path.read_text(encoding="utf-8").split("---", 2)[2]
    assert "mmbiz.qpic.cn" not in body
    links = BeautifulSoup(result.article.content_html, "html.parser").find_all("img")
    for img in links:
        assert img["src"].startswith(markdown_path(assets.name) + "/")
        assert (result.path.parent / unquote(img["src"])).is_file()


def test_unknown_error_page_is_reported():
    with pytest.raises(ArticleUnavailable, match="chksm"):
        check_article_page(load("unknown-error"))


def test_param_error_page_is_reported():
    with pytest.raises(ArticleUnavailable, match="参数错误"):
        check_article_page(load("param-error"))


def test_real_verification_page_writes_nothing(tmp_path):
    page = load("verify")
    with pytest.raises(VerificationRequired):
        check_article_page(page)
    with pytest.raises(VerificationRequired):
        ArticleDownloader(output_dir=str(tmp_path), fetcher=FakeFetcher(page)).download(BARE_URL)
    assert list(tmp_path.iterdir()) == []


def test_markdown_path_escapes_only_link_breaking_chars():
    assert markdown_path("2024-01-01_标题 (上).assets/001.png") == "2024-01-01_标题%20%28上%29.assets/001.png"
