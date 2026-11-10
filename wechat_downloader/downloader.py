"""
单篇文章下载：抓取 -> 解析 -> 下载图片 -> 写出 Markdown
"""
import dataclasses
import hashlib
import re
import shutil
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qs, quote, urlsplit

from bs4 import BeautifulSoup

from .fetch import Fetcher, WeChatError
from .parse import CHINA_TZ, Article, ParseError, parse_article
from .render import render_markdown

_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_filename(name: str, max_length: int = 80, max_bytes: int = 150) -> str:
    """max_bytes 按 UTF-8 计：多数文件系统限制单个文件名 255 字节，还要给日期、ID 和 .assets 后缀留余量"""
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip().strip(".")
    name = name[:max_length]
    while len(name.encode("utf-8")) > max_bytes:
        name = name[:-1]
    name = name.rstrip(" .")
    if not name or name.upper() in _WINDOWS_RESERVED:
        name = f"_{name}" if name else "未命名"
    return name


def article_id(article: Article) -> str:
    """
    由链接派生的 8 位稳定标识：同一篇文章（同 biz+mid+idx，或同一短链接）总是相同，
    不同文章即使同号同日同标题也不同。
    """
    parts = urlsplit(article.url)
    query = parse_qs(parts.query)
    mid, idx = query.get("mid", [""])[0], query.get("idx", ["1"])[0]
    if mid:
        biz = article.biz or query.get("__biz", [""])[0]
        key = f"{biz}:{mid}:{idx}"
    elif parts.path.startswith("/s/"):
        key = parts.path[len("/s/"):].strip("/")
    else:
        key = article.url
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]


_MARKDOWN_UNSAFE = set(" ()[]<>%#")


def markdown_path(path: str) -> str:
    """文章名里常有空格和括号，不编码的话 Markdown 链接会断；中文保持原样以便阅读"""
    return "".join(quote(ch) if ch in _MARKDOWN_UNSAFE else ch for ch in path)


_IMAGE_EXTENSIONS = {
    "jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "gif": ".gif",
    "webp": ".webp", "bmp": ".bmp", "svg+xml": ".svg", "svg": ".svg",
}


def image_extension(url: str, content_type: str = "") -> str:
    """优先按 Content-Type 判断；微信图片链接里的 wx_fmt 经常是 other，不可靠"""
    mime = content_type.split(";")[0].strip().lower()
    if mime.startswith("image/") and mime[len("image/"):] in _IMAGE_EXTENSIONS:
        return _IMAGE_EXTENSIONS[mime[len("image/"):]]
    wx_fmt = parse_qs(urlsplit(url).query).get("wx_fmt", [""])[0].lower()
    return _IMAGE_EXTENSIONS.get(wx_fmt, ".jpg")


@dataclass
class DownloadResult:
    article: Article
    path: Path
    failed_images: List[str] = field(default_factory=list)


class ArticleDownloader:
    def __init__(self, output_dir: str = "downloads", fetcher: Optional[Fetcher] = None,
                 download_images: bool = True):
        self.output_dir = Path(output_dir)
        self.fetcher = fetcher or Fetcher()
        self.download_images = download_images

    def fetch(self, url: str) -> Article:
        return parse_article(self.fetcher.get_article_html(url), url)

    def download(self, url: str) -> DownloadResult:
        return self.save(self.fetch(url))

    def article_stem(self, article: Article) -> str:
        when = article.publish_time or datetime.now(tz=CHINA_TZ)
        return f"{when.strftime('%Y-%m-%d')}_{safe_filename(article.title)}_{article_id(article)}"

    def save(self, article: Article, download_images: Optional[bool] = None) -> DownloadResult:
        if download_images is None:
            download_images = self.download_images
        if not BeautifulSoup(article.content_html, "html.parser").get_text(strip=True) and not article.images:
            raise ParseError("文章正文为空，未写入文件")
        folder = self.output_dir / safe_filename(article.account_name or "未知公众号")
        folder.mkdir(parents=True, exist_ok=True)
        stem = self.article_stem(article)
        failed: List[str] = []
        if download_images and article.images:
            local, failed = self._save_images(article.images, folder, f"{stem}.assets")
            article = dataclasses.replace(article, content_html=_replace_image_src(article.content_html, local))
        md_path = folder / f"{stem}.md"
        md_path.write_text(render_markdown(article), encoding="utf-8")
        return DownloadResult(article=article, path=md_path, failed_images=failed)

    def _save_images(self, urls: List[str], folder: Path, assets_name: str):
        """返回 (原始链接 -> Markdown 里用的相对路径, 下载失败的链接)；失败的图片保留原始链接"""
        assets = folder / assets_name
        # 重复下载同一篇时清掉上次的图片，保证结果和第一次一致
        if assets.is_dir():
            shutil.rmtree(assets)
        local: Dict[str, str] = {}
        failed: List[str] = []
        for index, url in enumerate(urls, 1):
            try:
                data, content_type = self.fetcher.get_image(url)
            except WeChatError:
                failed.append(url)
                continue
            name = f"{index:03d}{image_extension(url, content_type)}"
            assets.mkdir(exist_ok=True)
            (assets / name).write_bytes(data)
            local[url] = markdown_path(f"{assets_name}/{name}")
        return local, failed

    def download_article(self, article_data: Dict, account_name: str = "",
                         download_images: Optional[bool] = None) -> Optional[Path]:
        """兼容旧接口：接收 WeChatAPI.get_article_content() 返回的字典"""
        publish_time = article_data.get("publish_time") or 0
        article = Article(
            url=article_data.get("url", ""),
            title=article_data.get("title") or "未命名文章",
            author=article_data.get("author", ""),
            account_name=account_name or article_data.get("account_name", ""),
            biz=article_data.get("biz", ""),
            user_name=article_data.get("user_name", ""),
            publish_time=datetime.fromtimestamp(publish_time, tz=CHINA_TZ) if publish_time else None,
            description=article_data.get("description", ""),
            cover=article_data.get("cover", ""),
            source_url=article_data.get("source_url", ""),
            content_html=article_data.get("content", ""),
            images=list(article_data.get("images", [])),
        )
        return self.save(article, download_images=download_images).path


def _replace_image_src(content_html: str, local: Dict[str, str]) -> str:
    if not local:
        return content_html
    soup = BeautifulSoup(content_html, "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src")
        if src in local:
            img["src"] = local[src]
    return str(soup)
