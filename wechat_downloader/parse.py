"""
文章页面解析：元数据 + 清洗后的正文 HTML
"""
import copy
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from .fetch import WeChatError, normalize_url

CHINA_TZ = timezone(timedelta(hours=8))

_JS_STRING = re.compile(r"""(["'])((?:\\.|(?!\1).)*)\1""", re.DOTALL)
_JS_ESCAPE = re.compile(r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)", re.DOTALL)
_SIMPLE_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}

# 正文里这些块不是文章内容（公众号卡片、小程序、投票等），转 Markdown 只会留下乱码文本
_NON_CONTENT_SELECTORS = (
    "script", "style", "noscript", "iframe",
    "mp-common-profile", "mp-common-mpaudio", "mp-common-videosnap",
    "mp-miniprogram", "mpvoice", "qqmusic", "mpvote",
    "ul.code-snippet__line-index",
)


class ParseError(WeChatError):
    """页面结构无法识别"""


@dataclass
class Article:
    url: str
    title: str
    author: str = ""
    account_name: str = ""
    biz: str = ""
    user_name: str = ""
    mid: str = ""
    idx: str = ""
    publish_time: Optional[datetime] = None
    description: str = ""
    cover: str = ""
    source_url: str = ""
    content_html: str = ""
    images: List[str] = field(default_factory=list)

    @property
    def publish_timestamp(self) -> int:
        return int(self.publish_time.timestamp()) if self.publish_time else 0

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "author": self.author,
            "account_name": self.account_name,
            "biz": self.biz,
            "user_name": self.user_name,
            "mid": self.mid,
            "idx": self.idx,
            "publish_time": self.publish_timestamp,
            "description": self.description,
            "cover": self.cover,
            "source_url": self.source_url,
            "content": self.content_html,
            "images": list(self.images),
        }


def _decode_js_string(raw: str) -> str:
    def repl(match: re.Match) -> str:
        esc = match.group(1)
        if esc[0] in "xu" and len(esc) > 1:
            return chr(int(esc[1:], 16))
        return _SIMPLE_ESCAPES.get(esc, esc)

    return _join_surrogates(html.unescape(_JS_ESCAPE.sub(repl, raw))).strip()


def _join_surrogates(text: str) -> str:
    """JS 用 UTF-16 代理对表示 emoji（\\uD83D\\uDE00），逐个 chr() 后要合并；孤立代理换成 U+FFFD，否则写文件时会报错"""
    return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


def extract_js_var(page: str, name: str) -> str:
    """
    读取 `var name = ...` 的字符串值，兼容微信页面里的几种写法：
      var biz = "" || "MzI4NjAxNjY4Nw==";
      var nickname = htmlDecode("阮一峰的网络日志");
      var msg_title = '标题'.html(false);
      var create_time = "1711672635" * 1;
    同名变量出现多次时取第一个非空的字面量。
    """
    pattern = re.compile(r"\bvar\s+" + re.escape(name) + r"\s*=\s*")
    for match in pattern.finditer(page):
        pos = match.end()
        while True:
            pos = _skip(page, pos, ("htmlDecode(",))
            literal = _JS_STRING.match(page, pos)
            if not literal:
                break
            value = _decode_js_string(literal.group(2))
            if value:
                return value
            pos = _skip(page, literal.end(), (")",))
            if not page.startswith("||", pos):
                break
            pos += 2
    return ""


def _skip(page: str, pos: int, tokens) -> int:
    while True:
        while pos < len(page) and page[pos] in " \t":
            pos += 1
        for token in tokens:
            if page.startswith(token, pos):
                pos += len(token)
                break
        else:
            return pos


def _text(soup: BeautifulSoup, selector: str) -> str:
    node = soup.select_one(selector)
    return node.get_text(" ", strip=True) if node else ""


def _meta(soup: BeautifulSoup, prop: str) -> str:
    node = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    return (node.get("content") or "").strip() if node else ""


def _parse_time(page: str) -> Optional[datetime]:
    for name in ("create_time", "ct"):
        value = extract_js_var(page, name)
        if value.isdigit():
            return datetime.fromtimestamp(int(value), tz=CHINA_TZ)
    return None


def _digits(page: str, *names: str) -> str:
    for name in names:
        value = extract_js_var(page, name)
        if value.isdigit():
            return value
    return ""


def _normalize_src(src: str) -> str:
    src = html.unescape(src.strip())
    if src.startswith("//"):
        src = "https:" + src
    if src.startswith("http://mmbiz.qpic.cn"):
        src = "https://" + src[len("http://"):]
    return src


def _clean_images(content: Tag) -> List[str]:
    """微信图片是懒加载：真实地址在 data-src，src 往往是占位图或为空"""
    images: List[str] = []
    for img in content.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        if not src or src.startswith("data:"):
            img.decompose()
            continue
        src = _normalize_src(src)
        alt = img.get("alt") or ""
        img.attrs = {"src": src}
        if alt and alt != "null":
            img["alt"] = alt
        if src not in images:
            images.append(src)
    return images


def _flatten_code_blocks(soup: BeautifulSoup, content: Tag) -> None:
    """
    微信代码块是 <pre><code>第1行</code><code>第2行</code>...</pre>，
    直接转换会把所有行挤成一行；这里合并成标准的单个 <code>，<br> 一律视为换行。
    """
    for pre in content.find_all("pre"):
        codes = pre.find_all("code") or [pre]
        lines = []
        for code in codes:
            for br in code.find_all("br"):
                br.replace_with("\n")
            line = code.get_text()
            # 逐行格式里空行写成 <code><br></code>，行尾的 <br> 只是占位
            if len(codes) > 1 and line.endswith("\n"):
                line = line[:-1]
            lines.append(line)
        text = "\n".join(lines)
        lang = (pre.get("data-lang") or "").strip()
        new_code = soup.new_tag("code")
        if lang:
            new_code["class"] = f"language-{lang}"
        new_code.string = text.rstrip("\n")
        pre.clear()
        pre.attrs = {}
        pre.append(new_code)


def _clean_content(soup: BeautifulSoup) -> Optional[Tag]:
    content = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
    if content is None:
        return None
    content = copy.copy(content)
    for selector in _NON_CONTENT_SELECTORS:
        for node in content.select(selector):
            node.decompose()
    for node in content.find_all(True):
        for attr in ("style", "class", "data-pm-slice", "data-tools", "data-id", "nodeleaf", "leaf"):
            node.attrs.pop(attr, None)
    content.attrs = {}
    return content


def parse_article(page: str, url: str) -> Article:
    soup = BeautifulSoup(page, "html.parser")

    content = _clean_content(soup)
    if content is None:
        item_type = extract_js_var(page, "item_show_type")
        hint = f"（item_show_type={item_type}）" if item_type else ""
        raise ParseError(
            f"未找到文章正文{hint}。可能是图片/视频/音频分享类消息，第一阶段暂不支持。"
        )

    _flatten_code_blocks(soup, content)
    images = _clean_images(content)

    title = (
        extract_js_var(page, "msg_title")
        or _text(soup, "#activity-name")
        or _meta(soup, "og:title")
        or "未命名文章"
    )
    account_name = extract_js_var(page, "nickname") or _text(soup, "#js_name")
    author = extract_js_var(page, "author") or _text(soup, "#js_author_name")

    if not content.get_text(strip=True) and not images:
        raise ParseError("文章正文为空")

    return Article(
        url=normalize_url(extract_js_var(page, "msg_link") or url),
        title=title,
        author=author,
        account_name=account_name,
        biz=extract_js_var(page, "biz"),
        user_name=extract_js_var(page, "user_name"),
        mid=_digits(page, "mid", "appmsgid"),
        idx=_digits(page, "idx", "itemidx"),
        publish_time=_parse_time(page),
        description=extract_js_var(page, "msg_desc"),
        cover=_normalize_src(extract_js_var(page, "msg_cdn_url")),
        source_url=extract_js_var(page, "msg_source_url"),
        content_html=str(content),
        images=images,
    )
