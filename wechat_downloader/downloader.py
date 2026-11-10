"""
单篇文章下载：抓取 -> 解析 -> 写出 Markdown（图片保留微信原始链接，不下载到本地）
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .fetch import Fetcher
from .parse import CHINA_TZ, Article, parse_article
from .render import render_markdown

_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_filename(name: str, max_length: int = 80) -> str:
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip().strip(".")
    name = name[:max_length].rstrip(" .")
    if not name or name.upper() in _WINDOWS_RESERVED:
        name = f"_{name}" if name else "未命名"
    return name


@dataclass
class DownloadResult:
    article: Article
    path: Path


class ArticleDownloader:
    def __init__(self, output_dir: str = "downloads", fetcher: Optional[Fetcher] = None):
        self.output_dir = Path(output_dir)
        self.fetcher = fetcher or Fetcher()

    def fetch(self, url: str) -> Article:
        return parse_article(self.fetcher.get_article_html(url), url)

    def download(self, url: str) -> DownloadResult:
        return self.save(self.fetch(url))

    def article_stem(self, article: Article) -> str:
        when = article.publish_time or datetime.now(tz=CHINA_TZ)
        return f"{when.strftime('%Y-%m-%d')}_{safe_filename(article.title)}"

    def save(self, article: Article) -> DownloadResult:
        folder = self.output_dir / safe_filename(article.account_name or "未知公众号")
        folder.mkdir(parents=True, exist_ok=True)
        md_path = folder / f"{self.article_stem(article)}.md"
        md_path.write_text(render_markdown(article), encoding="utf-8")
        return DownloadResult(article=article, path=md_path)

    def download_article(self, article_data: Dict, account_name: str = "",
                         download_images: bool = False) -> Optional[Path]:
        """兼容旧接口：接收 WeChatAPI.get_article_content() 返回的字典；download_images 已不再支持，参数仅为兼容保留"""
        publish_time = article_data.get("publish_time") or 0
        article = Article(
            url=article_data.get("url", ""),
            title=article_data.get("title") or "未命名文章",
            author=article_data.get("author", ""),
            account_name=account_name or article_data.get("account_name", ""),
            biz=article_data.get("biz", ""),
            publish_time=datetime.fromtimestamp(publish_time, tz=CHINA_TZ) if publish_time else None,
            description=article_data.get("description", ""),
            cover=article_data.get("cover", ""),
            source_url=article_data.get("source_url", ""),
            content_html=article_data.get("content", ""),
            images=list(article_data.get("images", [])),
        )
        return self.save(article).path
