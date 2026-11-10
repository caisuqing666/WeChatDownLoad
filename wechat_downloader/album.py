"""
公众号合集（appmsgalbum）：不登录翻页拿到合集里的全部文章链接
"""
import html
import json
import os
import random
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlsplit

import requests

from .fetch import VerificationRequired, WeChatError, normalize_url

ALBUM_ENDPOINT = "https://mp.weixin.qq.com/mp/appmsgalbum"
PAGE_SIZE = 20  # 接口每页最多返回 20 条，count 再大也没用
MIN_LIST_DELAY = 3.0
PAGE_RETRIES = 2
# 版本 1 的缓存在空页或整页重复时也会标记完成，不能信任，读到时从头重新翻
CACHE_VERSION = 2
RET_BAD_ALBUM = 10004


class AlbumError(WeChatError):
    """合集接口返回了 ret≠0 等明确错误"""


class AlbumPaginationError(WeChatError):
    """continue_flag=1 但重试后仍没有新文章"""


def parse_album_url(url: str) -> Tuple[str, str]:
    """从合集链接取 __biz 和 album_id；链接可以带 &amp; 和 #wechat_redirect"""
    query = parse_qs(urlsplit(html.unescape(url.strip())).query)
    biz = query.get("__biz", [""])[0].strip()
    album_id = query.get("album_id", [""])[0].strip()
    if not biz or not album_id:
        raise WeChatError("合集链接里缺少 __biz 或 album_id，"
                          "应形如 https://mp.weixin.qq.com/mp/appmsgalbum?__biz=...&action=getalbum&album_id=...")
    if not album_id.isdigit():
        raise WeChatError(f"合集链接里的 album_id 不是数字：{album_id}")
    return biz, album_id


def album_params(biz: str, album_id: str, cursor: Optional[Tuple[str, str]] = None) -> Dict[str, str]:
    params = {"action": "getalbum", "__biz": biz, "album_id": album_id, "count": str(PAGE_SIZE),
              "is_reverse": "0", "f": "json"}
    if cursor:
        params["begin_msgid"], params["begin_itemidx"] = cursor
    return params


def parse_album_response(content_type: str, text: str) -> Dict:
    """
    返回 getalbum_resp。要的是 JSON，拿到 HTML 或其他非 JSON 内容就当作被风控（验证页），
    拿到 JSON 但 ret≠0 是接口明确拒绝。
    """
    try:
        data = json.loads(text) if "html" not in content_type.lower() else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("base_resp"), dict):
        raise VerificationRequired(
            "合集接口没有返回 JSON（多半是“环境异常”验证页）：请求过于频繁或当前网络被限制。"
            "已停止，请稍后（如半小时后）重新运行同一命令，已拿到的列表会接着翻"
        )
    ret = data["base_resp"].get("ret")
    if str(ret) == str(RET_BAD_ALBUM):
        raise AlbumError(f"合集接口返回 ret={ret}：album_id 错误或合集不存在，请检查链接")
    if str(ret) != "0":
        raise AlbumError(f"合集接口返回 ret={ret}：接口拒绝了不带凭证的请求，暂时无法通过合集获取列表")
    resp = data.get("getalbum_resp")
    return resp if isinstance(resp, dict) else None


def page_articles(resp: Dict) -> List[Dict]:
    items = resp.get("article_list") or []
    if isinstance(items, dict):  # 只有一条时可能不是数组
        items = [items]
    return [item for item in items if isinstance(item, dict) and item.get("msgid") and item.get("url")]


@dataclass
class AlbumListing:
    biz: str
    album_id: str
    title: str = ""
    nickname: str = ""
    article_count: int = 0
    articles: List[Dict] = field(default_factory=list)
    cursor: Optional[Tuple[str, str]] = None
    complete: bool = False
    requests: int = 0

    @property
    def urls(self) -> List[str]:
        return [a["url"] for a in self.articles]

    def to_json(self) -> Dict:
        return {
            "version": CACHE_VERSION, "biz": self.biz, "album_id": self.album_id, "title": self.title,
            "nickname": self.nickname, "article_count": self.article_count, "complete": self.complete,
            "cursor": list(self.cursor) if self.cursor else None, "articles": self.articles,
        }

    @classmethod
    def from_json(cls, data: Dict) -> "AlbumListing":
        cursor = data.get("cursor")
        return cls(
            biz=data["biz"], album_id=data["album_id"], title=data.get("title", ""),
            nickname=data.get("nickname", ""), article_count=int(data.get("article_count") or 0),
            articles=[a for a in data.get("articles", []) if isinstance(a, dict) and a.get("url")],
            cursor=(str(cursor[0]), str(cursor[1])) if isinstance(cursor, list) and len(cursor) == 2 else None,
            complete=bool(data.get("complete")),
        )


def cache_path(output_dir: Path, album_id: str) -> Path:
    return output_dir / f".wechat_album_{album_id}.json"


def load_cache(output_dir: Path, biz: str, album_id: str) -> Optional[AlbumListing]:
    path = cache_path(output_dir, album_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
            print(f"! 合集列表缓存 {path} 是旧版本，无法确认是否翻完，将从头重新翻页（已下载的文章仍会跳过）")
            return None
        listing = AlbumListing.from_json(data)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"! 合集列表缓存 {path} 无法读取（{e}），将重新翻页")
        return None
    if listing.biz != biz or listing.album_id != album_id:
        return None
    return listing


def save_cache(output_dir: Path, listing: AlbumListing) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(output_dir, listing.album_id)
    fd, tmp_name = tempfile.mkstemp(dir=output_dir, prefix=f"{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(listing.to_json(), f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _entry(item: Dict) -> Dict:
    return {
        "msgid": str(item["msgid"]), "itemidx": str(item.get("itemidx") or "1"),
        "title": html.unescape(str(item.get("title", ""))), "url": normalize_url(str(item["url"])),
        "create_time": str(item.get("create_time", "")),
    }


def _page_problem(resp: Optional[Dict], seen) -> Tuple[str, List[Dict]]:
    """
    只有 continue_flag 明确是 "0"（翻完）或 "1"（还有）的页才可信；其他情况整页丢弃，游标不动。
    返回 (异常原因, 本页新文章)，正常页的异常原因为空串。
    """
    if resp is None:
        return "接口返回成功但缺少 getalbum_resp", []
    flag = resp.get("continue_flag")
    if str(flag) not in ("0", "1") or isinstance(flag, bool):
        return f"接口返回的 continue_flag 异常（{'缺失' if flag is None else repr(flag)}）", []
    new, keys = [], set(seen)
    for item in page_articles(resp):
        entry = _entry(item)
        key = (entry["msgid"], entry["itemidx"])
        if key not in keys:
            keys.add(key)
            new.append(entry)
    if str(flag) == "1" and not new:
        return "接口说还有下一页，但没有返回新文章", []
    return "", new


def list_album(get_page: Callable[[Dict[str, str]], Tuple[str, str]], listing: AlbumListing,
               delay: float = 3.0, jitter: float = 2.0, on_page: Optional[Callable[[AlbumListing], None]] = None,
               sleep: Optional[Callable[[float], None]] = None,
               uniform: Optional[Callable[[float, float], float]] = None) -> AlbumListing:
    """
    从 listing.cursor（为空则从首页）翻到底，结果追加到 listing。
    游标是上一页最后一条的 msgid+itemidx，必须精确：itemidx 不对时接口返回空列表却仍说 continue_flag=1。
    只有 continue_flag 明确为 0 才算翻完。continue_flag=1 却没有新文章（空列表或整页重复），
    或缺 getalbum_resp / continue_flag 缺失或不是 0/1，都是分页异常：整页丢弃、游标不动，
    按退避重试 PAGE_RETRIES 次，仍然异常就抛 AlbumPaginationError，listing 保持未完成。
    每页拿到新文章后调用 on_page，便于中途停下后续翻。两次请求之间至少等 MIN_LIST_DELAY 秒。
    """
    sleep = sleep or time.sleep
    uniform = uniform or random.uniform
    seen = {(a["msgid"], a["itemidx"]) for a in listing.articles}
    failures = 0
    while not listing.complete:
        if listing.requests:
            sleep(max(delay, MIN_LIST_DELAY) * 2 ** failures + (uniform(0, jitter) if jitter > 0 else 0))
        resp = parse_album_response(*get_page(album_params(listing.biz, listing.album_id, listing.cursor)))
        listing.requests += 1
        problem, new = _page_problem(resp, seen)
        if problem:
            failures += 1
            if failures > PAGE_RETRIES:
                raise AlbumPaginationError(
                    f"合集列表翻页异常：{problem}，连续 {failures} 次都是这样"
                    f"（已拿到 {len(listing.articles)} 篇）。列表已按未完成保存，请稍后重新运行同一命令，"
                    f"会从上次的位置接着翻；一直如此可加 --refresh-album 从头翻"
                )
            continue
        failures = 0
        info = resp.get("base_info")
        if isinstance(info, dict) and info.get("title"):
            listing.title = html.unescape(str(info.get("title", "")))
            listing.nickname = html.unescape(str(info.get("nickname", "")))
            listing.article_count = int(info.get("article_count") or 0)
        for entry in new:
            seen.add((entry["msgid"], entry["itemidx"]))
            listing.articles.append(entry)
        if new:
            listing.cursor = (new[-1]["msgid"], new[-1]["itemidx"])
        listing.complete = str(resp["continue_flag"]) == "0"
        if on_page:
            on_page(listing)
    return listing


def fetch_album_listing(session: requests.Session, output_dir: Path, album_url: str, delay: float, jitter: float,
                        refresh: bool = False, timeout: float = 20) -> AlbumListing:
    """读缓存（已翻完的直接用，没翻完的从游标接着翻），否则从头翻；每页结束写一次缓存"""
    biz, album_id = parse_album_url(album_url)
    listing = None if refresh else load_cache(output_dir, biz, album_id)
    if listing and listing.complete:
        print(f"使用缓存的合集列表：{cache_path(output_dir, album_id)}（共 {len(listing.articles)} 篇，"
              f"加 --refresh-album 重新获取）")
        return listing
    if listing:
        print(f"接着上次的进度翻合集列表（已有 {len(listing.articles)} 篇）")
    else:
        listing = AlbumListing(biz=biz, album_id=album_id)

    def get_page(params: Dict[str, str]) -> Tuple[str, str]:
        try:
            response = session.get(ALBUM_ENDPOINT, params=params, timeout=timeout,
                                   headers={"Accept": "application/json, text/plain, */*"})
            response.raise_for_status()
        except requests.RequestException as e:
            raise WeChatError(f"请求合集列表失败：{e}") from e
        response.encoding = "utf-8"
        return response.headers.get("Content-Type", ""), response.text

    def on_page(current: AlbumListing) -> None:
        save_cache(output_dir, current)
        print(f"  合集列表第 {current.requests} 页，累计 {len(current.articles)} 篇")

    return list_album(get_page, listing, delay=delay, jitter=jitter, on_page=on_page)
