"""
HTML 正文 -> Markdown
"""
import json
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

from .parse import CHINA_TZ, Article


def _code_language(el) -> Optional[str]:
    code = el.find("code")
    for cls in (code.get("class") or []) if code else []:
        if cls.startswith("language-"):
            return cls[len("language-"):]
    return None


class _WeChatConverter(MarkdownConverter):
    # markdownify 默认把 <code> 里的文本再转义一次，会破坏代码块中的 * _ #
    def convert_pre(self, el, text, parent_tags):
        code = el.find("code")
        body = code.get_text() if code else el.get_text()
        lang = _code_language(el) or ""
        return f"\n\n```{lang}\n{body}\n```\n\n"


def html_to_markdown(content_html: str) -> str:
    soup = BeautifulSoup(content_html, "html.parser")
    markdown = _WeChatConverter(heading_style="ATX", bullets="-").convert_soup(soup)
    markdown = markdown.replace("\u00a0", " ")
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip() + "\n"


def _yaml_value(value) -> str:
    # JSON 字符串是合法的 YAML 标量，可以安全处理冒号、引号、# 等字符
    return json.dumps(value, ensure_ascii=False)


def front_matter(article: Article) -> str:
    fields = {
        "title": article.title,
        "author": article.author,
        "account": article.account_name,
        "biz": article.biz,
        "url": article.url,
        "source_url": article.source_url,
        "publish_time": article.publish_time.isoformat() if article.publish_time else "",
        "description": article.description,
        "cover": article.cover,
        "downloaded_at": datetime.now(tz=CHINA_TZ).isoformat(timespec="seconds"),
    }
    lines = [f"{key}: {_yaml_value(value)}" for key, value in fields.items() if value]
    return "---\n" + "\n".join(lines) + "\n---\n"


def render_markdown(article: Article) -> str:
    body = html_to_markdown(article.content_html)
    return f"{front_matter(article)}\n# {article.title}\n\n{body}"
