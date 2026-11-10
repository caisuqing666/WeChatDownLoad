"""
网络请求：文章页面抓取与异常页面识别
"""
import html
import re
from typing import Tuple
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 用微信内置浏览器的 UA 请求文章页只会拿到一个 2KB 的跳转壳，必须用桌面浏览器 UA
DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

VERIFICATION_MARKERS = ("完成验证后即可继续访问", "环境异常")
UNAVAILABLE_MARKERS = (
    "该内容已被发布者删除",
    "此内容因违规无法查看",
    "此内容发送失败无法查看",
    "该公众号已迁移",
    "内容已被删除",
)
INVALID_LINK_MARKERS = ("未知错误，请稍后再试", "失效的验证页面")
# 微信的错误/提示页统一用 weui-msg__title 显示原因，如“参数错误”“链接已过期”
_MSG_TITLE = re.compile(r'class="weui-msg__title[^"]*"[^>]*>([^<]*)<')


class WeChatError(Exception):
    """可向用户直接展示的错误"""


class VerificationRequired(WeChatError):
    """微信返回了“环境异常/验证”页面，通常是请求过快或 IP 被限制"""


class ArticleUnavailable(WeChatError):
    """文章已删除、违规或公众号迁移"""


def normalize_url(url: str) -> str:
    """
    清理用户粘贴的文章链接：
    - 还原 CSV/HTML 里常见的 &amp;
    - 去掉 #wechat_redirect 之类的锚点
    - 统一为 https
    """
    url = html.unescape(url.strip())
    parts = urlsplit(url)
    if not parts.scheme:
        parts = urlsplit("https://" + url.lstrip("/"))
    scheme = "https" if parts.scheme in ("http", "https") else parts.scheme
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, ""))


def check_article_page(page: str) -> None:
    """识别验证页和不可用页；正文存在时不做判断，避免误伤正文里恰好出现的字样"""
    if 'id="js_content"' in page:
        return
    if any(marker in page for marker in VERIFICATION_MARKERS):
        raise VerificationRequired(
            "微信返回了“环境异常”验证页：请求过于频繁或当前网络被限制。"
            "请稍后重试，或在浏览器打开该链接完成验证后再下载。"
        )
    for marker in UNAVAILABLE_MARKERS:
        if marker in page:
            raise ArticleUnavailable(f"文章不可用：{marker}")
    if any(marker in page for marker in INVALID_LINK_MARKERS):
        raise ArticleUnavailable(
            "微信返回了“未知错误，请稍后再试”页面：链接可能不完整或已失效"
            "（例如长链接缺少 chksm 参数）。请从微信里复制完整链接，或改用 /s/ 短链接。"
        )
    notice = _MSG_TITLE.search(page)
    if notice and notice.group(1).strip():
        raise ArticleUnavailable(f"文章不可用：微信提示“{html.unescape(notice.group(1).strip())}”，请检查链接是否完整")


class Fetcher:
    def __init__(self, timeout: float = 20, retries: int = 3):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DESKTOP_UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        retry = Retry(
            total=retries,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=8)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_article_html(self, url: str) -> str:
        try:
            response = self.session.get(normalize_url(url), timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            raise WeChatError(f"请求文章失败：{e}") from e
        response.encoding = "utf-8"
        page = response.text
        check_article_page(page)
        return page

    def get_image(self, url: str) -> Tuple[bytes, str]:
        """返回图片内容和 Content-Type"""
        try:
            response = self.session.get(
                url, timeout=self.timeout, headers={"Referer": "https://mp.weixin.qq.com/"}
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise WeChatError(f"下载图片失败：{e}") from e
        content_type = response.headers.get("Content-Type", "")
        if content_type.startswith("text/"):
            raise WeChatError(f"下载图片失败：返回的是 {content_type} 而不是图片")
        return response.content, content_type
