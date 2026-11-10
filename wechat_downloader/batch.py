"""
按链接清单逐篇下载：限速、断点续传、已下载的自动跳过
"""
import json
import os
import random
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .downloader import ArticleDownloader, DownloadResult, RollbackError, link_article_id
from .fetch import VerificationRequired, normalize_url
from .parse import CHINA_TZ

PROGRESS_FILE = ".wechat_progress.json"
PROGRESS_VERSION = 1


def read_url_file(path: str) -> List[str]:
    """逐行读链接，忽略空行和 # 开头的注释；同一篇文章（同一链接或同一长链接 ID）只保留第一次出现"""
    urls: List[str] = []
    seen = set()
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        url = normalize_url(line)
        key = link_article_id(url) or url
        if key not in seen:
            seen.add(key)
            urls.append(url)
    return urls


class Progress:
    """
    输出目录下的进度文件，以规范化后的链接为键。
    每篇结束都整体重写一次：先写同目录临时文件再 os.replace，中断时旧进度文件保持完整。
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.path = output_dir / PROGRESS_FILE
        self.articles: Dict[str, Dict] = self._load()

    def _load(self) -> Dict[str, Dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            print(f"! 进度文件 {self.path} 无法读取（{e}），将重新记录；已下载的长链接文章仍会按文件跳过")
            return {}
        articles = data.get("articles") if isinstance(data, dict) else None
        return {k: v for k, v in articles.items() if isinstance(v, dict)} if isinstance(articles, dict) else {}

    def status(self, url: str) -> str:
        return self.articles.get(url, {}).get("status", "")

    def saved_path(self, url: str, *statuses: str) -> Optional[Path]:
        """状态在 statuses 里且文件还在时返回文件路径"""
        entry = self.articles.get(url)
        if not entry or entry.get("status") not in statuses or not entry.get("path"):
            return None
        path = self.output_dir / entry["path"]
        return path if path.is_file() else None

    def missing_images(self, url: str) -> List[str]:
        return list(self.articles.get(url, {}).get("failed_images", []))

    def mark_done(self, url: str, path: Path, article_id: str, title: str,
                  failed_images: Optional[List[str]] = None) -> None:
        """有图片没下载成功时记为 partial：正文已保存，但缺的图可以重下补齐"""
        entry = {
            "status": "partial" if failed_images else "done",
            "id": article_id,
            "path": path.relative_to(self.output_dir).as_posix(),
            "title": title,
            "updated_at": _now(),
        }
        if failed_images:
            entry["missing_images"] = len(failed_images)
            entry["failed_images"] = list(failed_images)
            entry["attempts"] = self.articles.get(url, {}).get("attempts", 0) + 1
        self.articles[url] = entry
        self.save()

    def mark_failed(self, url: str, error: str) -> None:
        attempts = self.articles.get(url, {}).get("attempts", 0) + 1
        self.articles[url] = {"status": "failed", "error": error, "attempts": attempts, "updated_at": _now()}
        self.save()

    def save(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        text = json.dumps({"version": PROGRESS_VERSION, "articles": self.articles}, ensure_ascii=False, indent=2)
        fd, tmp_name = tempfile.mkstemp(dir=self.output_dir, prefix=f"{PROGRESS_FILE}.", suffix=".tmp")
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            tmp.unlink(missing_ok=True)


def _now() -> str:
    return datetime.now(tz=CHINA_TZ).isoformat(timespec="seconds")


def find_existing(output_dir: Path, url: str) -> Optional[Path]:
    """长链接下载前就能算出文章 ID，按第一阶段的文件名规则 <日期>_<标题>_<ID>.md 找已有文件"""
    key = link_article_id(url)
    if not key:
        return None
    return next((p for p in output_dir.glob(f"*/*_{key}.md") if p.is_file()), None)


_REMOTE_IMAGE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")


def remote_images(md_path: Path) -> List[str]:
    """下载图片时成功的图都改成了本地相对路径，仍是 http 链接的就是当时没下载成功的"""
    try:
        return _REMOTE_IMAGE.findall(md_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return []


@dataclass
class BatchResult:
    total: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: List[Tuple[str, str]] = field(default_factory=list)
    partial: List[Tuple[str, Path, List[str]]] = field(default_factory=list)
    stopped: Optional[str] = None
    remaining: int = 0


def print_result(prefix: str, result: DownloadResult) -> None:
    print(f"{prefix}✓ {result.article.title}\n    → {result.path}")
    if result.failed_images:
        print(f"    ! {len(result.failed_images)} 张图片下载失败，已保留原始链接：")
        for image_url in result.failed_images:
            print(f"      {image_url}")
    if result.kept_images:
        print(f"    ! {len(result.kept_images)} 张图片这次下载失败，沿用了上次下载的本地文件：")
        for image_url in result.kept_images:
            print(f"      {image_url}")


def download_url_list(downloader: ArticleDownloader, urls: List[str], delay: float = 3.0, jitter: float = 2.0,
                      sleep: Optional[Callable[[float], None]] = None,
                      uniform: Optional[Callable[[float, float], float]] = None,
                      retry_images: bool = True) -> BatchResult:
    """
    逐篇下载。两次实际请求之间等待 delay + [0, jitter] 秒，跳过的文章不等待。
    遇到验证页立即停止（继续请求只会被限制得更久）；RollbackError 和中断照常向上抛出，进度保留。
    其他单篇失败记入进度文件后继续，下次运行会重试。
    缺图（partial）的文章默认重新下载：重下时这次又失败的图沿用上次的本地文件，已成功的图不会丢；
    retry_images=False 时把缺图文章当作已下载跳过。
    """
    sleep = sleep or time.sleep
    uniform = uniform or random.uniform
    output_dir = downloader.output_dir
    progress = Progress(output_dir)
    result = BatchResult(total=len(urls))
    requested = False
    try:
        for index, url in enumerate(urls, 1):
            prefix = f"[{index}/{len(urls)}] "
            existing = _skip_target(progress, output_dir, url, downloader.download_images, retry_images)
            if existing is not None:
                result.skipped += 1
                missing = progress.missing_images(url) if progress.status(url) == "partial" else []
                if missing:
                    result.partial.append((url, existing, missing))
                    print(f"{prefix}- 已下载（缺 {len(missing)} 张图，未重试），跳过：{existing}")
                else:
                    print(f"{prefix}- 已下载，跳过：{existing}")
                continue
            if progress.status(url) == "partial":
                print(f"{prefix}… 上次缺 {len(progress.missing_images(url))} 张图，重新下载")
            if requested and (delay > 0 or jitter > 0):
                sleep(delay + (uniform(0, jitter) if jitter > 0 else 0))
            requested = True
            try:
                saved = downloader.download(url)
            except VerificationRequired as e:
                print(f"{prefix}✗ {e}")
                result.stopped = str(e)
                result.remaining = len(urls) - index + 1
                break
            except RollbackError:
                raise
            except Exception as e:
                if getattr(e, "interrupted", False):
                    raise
                message = str(e) or repr(e)
                print(f"{prefix}✗ {url}\n    {message}")
                result.failed.append((url, message))
                progress.mark_failed(url, message)
            else:
                print_result(prefix, saved)
                progress.mark_done(url, saved.path, _id_from_stem(saved.path), saved.article.title,
                                   saved.failed_images)
                result.downloaded += 1
                if saved.failed_images:
                    result.partial.append((url, saved.path, list(saved.failed_images)))
    except BaseException:
        print(f"\n进度已保存到 {progress.path}，重新运行同一命令会跳过已下载的文章")
        raise
    return result


def _skip_target(progress: Progress, output_dir: Path, url: str,
                 download_images: bool, retry_images: bool) -> Optional[Path]:
    """返回可以跳过的已下载文件；缺图且要重试、失败过或没下载过的返回 None"""
    if not retry_images:
        existing = progress.saved_path(url, "done", "partial")
        if existing is not None:
            return existing
    else:
        existing = progress.saved_path(url, "done")
        if existing is not None:
            return existing
        if progress.saved_path(url, "partial") is not None:
            return None
    existing = find_existing(output_dir, url)
    if existing is None:
        return None
    missing = remote_images(existing) if download_images else []
    progress.mark_done(url, existing, link_article_id(url), existing.stem, missing)
    return None if missing and retry_images else existing


def _id_from_stem(path: Path) -> str:
    return path.stem.rsplit("_", 1)[-1]


def print_summary(result: BatchResult, progress_path: Path) -> None:
    print(f"\n完成：共 {result.total} 篇，新下载 {result.downloaded} 篇，跳过 {result.skipped} 篇，"
          f"失败 {len(result.failed)} 篇，缺图 {len(result.partial)} 篇")
    if result.failed:
        print("失败的文章（下次运行会重试）：")
        for url, message in result.failed:
            print(f"  {url}\n    {message}")
    if result.partial:
        print("缺图的文章（正文已保存，缺的图保留了微信原始链接；下次运行会重试，--no-retry-images 可关闭）：")
        for url, path, missing in result.partial:
            print(f"  {path}（缺 {len(missing)} 张）\n    {url}")
    if result.stopped:
        print(f"已停止：微信返回了验证页，还有 {result.remaining} 篇未处理。"
              f"请稍后（如半小时后）重新运行同一命令，已下载的会自动跳过")
    print(f"进度文件：{progress_path}")
