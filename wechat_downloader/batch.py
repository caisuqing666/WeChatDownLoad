"""
按链接清单逐篇下载：限速、断点续传、已下载的自动跳过
"""
import json
import os
import random
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

    def done_path(self, url: str) -> Optional[Path]:
        entry = self.articles.get(url)
        if not entry or entry.get("status") != "done" or not entry.get("path"):
            return None
        path = self.output_dir / entry["path"]
        return path if path.is_file() else None

    def mark_done(self, url: str, path: Path, article_id: str, title: str) -> None:
        self.articles[url] = {
            "status": "done",
            "id": article_id,
            "path": path.relative_to(self.output_dir).as_posix(),
            "title": title,
            "updated_at": _now(),
        }
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


@dataclass
class BatchResult:
    total: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: List[Tuple[str, str]] = field(default_factory=list)
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
                      uniform: Optional[Callable[[float, float], float]] = None) -> BatchResult:
    """
    逐篇下载。两次实际请求之间等待 delay + [0, jitter] 秒，跳过的文章不等待。
    遇到验证页立即停止（继续请求只会被限制得更久）；RollbackError 和中断照常向上抛出，进度保留。
    其他单篇失败记入进度文件后继续，下次运行会重试。
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
            existing = progress.done_path(url)
            if existing is None:
                existing = find_existing(output_dir, url)
                if existing is not None:
                    progress.mark_done(url, existing, link_article_id(url), existing.stem)
            if existing is not None:
                result.skipped += 1
                print(f"{prefix}- 已下载，跳过：{existing}")
                continue
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
                progress.mark_done(url, saved.path, _id_from_stem(saved.path), saved.article.title)
                result.downloaded += 1
    except BaseException:
        print(f"\n进度已保存到 {progress.path}，重新运行同一命令会跳过已下载的文章")
        raise
    return result


def _id_from_stem(path: Path) -> str:
    return path.stem.rsplit("_", 1)[-1]


def print_summary(result: BatchResult, progress_path: Path) -> None:
    print(f"\n完成：共 {result.total} 篇，新下载 {result.downloaded} 篇，跳过 {result.skipped} 篇，失败 {len(result.failed)} 篇")
    if result.failed:
        print("失败的文章（下次运行会重试）：")
        for url, message in result.failed:
            print(f"  {url}\n    {message}")
    if result.stopped:
        print(f"已停止：微信返回了验证页，还有 {result.remaining} 篇未处理。"
              f"请稍后（如半小时后）重新运行同一命令，已下载的会自动跳过")
    print(f"进度文件：{progress_path}")
