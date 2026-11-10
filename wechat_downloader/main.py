"""
主程序入口
"""
import argparse
import random
import sys
import time
from typing import List, Optional

from .album import fetch_album_listing
from .api import WeChatAPI
from .batch import PROGRESS_FILE, download_url_list, print_result, print_summary, read_url_file
from .downloader import ArticleDownloader, RollbackError
from .fetch import VerificationRequired, WeChatError


def get_token_from_clipboard() -> Optional[str]:
    try:
        import pyperclip
        return pyperclip.paste().strip()
    except ImportError:
        print("提示: 安装 pyperclip 可以自动从剪贴板读取token")
        print("     运行: pip install pyperclip")
        return None
    except Exception:
        return None


def download_many(downloader: ArticleDownloader, urls: List[str], interval: float) -> int:
    """逐篇下载，返回失败篇数；遇到验证页立即停止，继续请求只会被限制得更久"""
    failed = 0
    for index, url in enumerate(urls, 1):
        prefix = f"[{index}/{len(urls)}] " if len(urls) > 1 else ""
        try:
            result = downloader.download(url)
        except VerificationRequired as e:
            print(f"{prefix}✗ {e}")
            return failed + len(urls) - index + 1
        except RollbackError:
            raise
        except WeChatError as e:
            print(f"{prefix}✗ {url}\n    {e}")
            failed += 1
        else:
            print_result(prefix, result)
        if index < len(urls) and interval > 0:
            time.sleep(interval)
    return failed


EXIT_INTERRUPTED = 130


def main(argv: Optional[List[str]] = None) -> int:
    """
    回滚失败时停止全部下载：磁盘上有需要手动恢复的备份，继续下载没有意义。
    期间收到过 Ctrl+C 则按惯例以 130 退出，否则以 1 退出。
    """
    try:
        return _main(argv)
    except RollbackError as e:
        print(f"✗ {e}")
        if e.backup_path is not None:
            print(f"    旧图片备份：{e.backup_path}")
        return EXIT_INTERRUPTED if e.interrupted else 1
    except KeyboardInterrupt:
        print("\n已中断")
        return EXIT_INTERRUPTED
    except Exception as e:
        if not getattr(e, "interrupted", False):
            raise
        print(f"✗ 保存失败：{e!r}（期间收到过中断，已停止）")
        return EXIT_INTERRUPTED


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description='微信公众号文章下载工具：把文章保存为 Markdown，图片下载到本地',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 下载单篇文章（支持 /s/xxx 短链接）
  python -m wechat_downloader.main "https://mp.weixin.qq.com/s/xxx"

  # 一次下载多篇
  python -m wechat_downloader.main URL1 URL2 URL3 -o ~/Documents/公众号

  # 按链接清单批量下载（每行一个链接，# 开头为注释），中断后重新运行会跳过已下载的
  python -m wechat_downloader.main --urls links.txt -o ~/Documents/公众号 --delay 5

  # 下载整个公众号合集（不需要登录），列表缓存在输出目录，中断后重新运行会接着下
  python -m wechat_downloader.main --album "https://mp.weixin.qq.com/mp/appmsgalbum?__biz=...&action=getalbum&album_id=..."

  # 用历史文章接口批量下载（需要从微信客户端抓到的 token，见 README）
  python -m wechat_downloader.main --url URL --token TOKEN --batch --count 10
        """
    )
    parser.add_argument('urls', nargs='*', metavar='URL', help='文章链接，可传多个')
    parser.add_argument('--url', '-u', action='append', default=[], help='文章链接（可重复，兼容旧用法）')
    parser.add_argument('--output', '-o', default='downloads', help='输出目录（默认: downloads）')
    parser.add_argument('--no-images', action='store_true', help='不下载图片，Markdown 里保留微信原始图片链接')
    parser.add_argument('--interval', type=float, default=2.0, help='多篇下载之间的间隔秒数（默认: 2）')
    parser.add_argument('--urls', dest='urls_file', metavar='FILE',
                        help=f'链接清单文件：每行一个链接，忽略空行和 # 注释；进度记在输出目录的 {PROGRESS_FILE}')
    parser.add_argument('--album', metavar='ALBUM_URL',
                        help='公众号合集链接（mp/appmsgalbum?__biz=...&album_id=...）：不登录翻页拿到全部文章后批量下载')
    parser.add_argument('--refresh-album', action='store_true', help='忽略输出目录里缓存的合集列表，重新翻页')
    parser.add_argument('--delay', type=float, default=3.0,
                        help='--urls/--album 模式两次请求之间的基础等待秒数（默认: 3；合集列表请求至少 3 秒）')
    parser.add_argument('--jitter', type=float, default=2.0, help='--urls/--album 模式在基础等待上再随机加 0~N 秒（默认: 2）')
    parser.add_argument('--no-retry-images', action='store_true',
                        help='--urls/--album 模式不重试上次有图片下载失败的文章（默认会重新下载补齐缺图）')
    parser.add_argument('--token', '-t', help='历史文章接口 token（仅 --batch 使用）')
    parser.add_argument('--token-clipboard', action='store_true', help='从剪贴板读取token')
    parser.add_argument('--batch', '-b', action='store_true', help='通过历史文章接口批量下载该公众号文章（需要 token）')
    parser.add_argument('--count', '-c', type=int, default=10, help='批量下载数量（默认: 10）')
    parser.add_argument('--offset', type=int, default=0, help='起始偏移量（默认: 0）')

    args = parser.parse_args(argv)
    urls = args.urls + args.url
    if args.urls_file and args.album:
        parser.error("--urls 和 --album 不能同时使用")
    if args.urls_file or args.album:
        if urls or args.batch:
            parser.error("--urls/--album 不能和直接给出的链接或 --batch 同时使用")
        if args.delay < 0 or args.jitter < 0:
            parser.error("--delay 和 --jitter 不能为负数")
        return _download_album(args) if args.album else _download_url_file(args)
    if not urls:
        parser.error("请至少提供一个文章链接")

    downloader = ArticleDownloader(output_dir=args.output, download_images=not args.no_images)

    if not args.batch:
        failed = download_many(downloader, urls, args.interval)
        if len(urls) > 1:
            print(f"\n完成：成功 {len(urls) - failed} 篇，失败 {failed} 篇")
        return 1 if failed else 0

    token = args.token
    if args.token_clipboard:
        token = get_token_from_clipboard() or token
    if not token:
        print("错误: 批量下载需要 token。不带 token 无法获取公众号历史文章列表"
              "（微信会返回 no session / 验证页）。")
        return 1

    api = WeChatAPI(token=token)
    try:
        first = downloader.fetch(urls[0])
    except WeChatError as e:
        print(f"错误: 无法读取示例文章：{e}")
        return 1
    print(f"公众号: {first.account_name}  (ID: {first.biz})")

    articles = api.get_article_list(first.biz, offset=max(args.offset, 0), count=max(args.count, 1))
    if not articles:
        print("错误: 历史文章接口没有返回文章，token 可能已过期")
        return 1

    print(f"找到 {len(articles)} 篇文章\n")
    links = [a['link'] for a in articles if a.get('link')]
    failed = download_many(downloader, links, args.interval)
    print(f"\n完成：成功 {len(links) - failed} 篇，失败 {failed} 篇")
    return 1 if failed else 0


def _download_url_file(args) -> int:
    try:
        urls = read_url_file(args.urls_file)
    except (OSError, UnicodeDecodeError) as e:
        print(f"错误: 无法读取链接清单 {args.urls_file}：{e}")
        return 1
    if not urls:
        print(f"错误: {args.urls_file} 里没有文章链接")
        return 1
    downloader = ArticleDownloader(output_dir=args.output, download_images=not args.no_images)
    result = download_url_list(downloader, urls, delay=args.delay, jitter=args.jitter,
                               retry_images=not args.no_retry_images)
    print_summary(result, downloader.output_dir / PROGRESS_FILE)
    return 1 if result.failed or result.partial or result.stopped else 0


def _download_album(args) -> int:
    downloader = ArticleDownloader(output_dir=args.output, download_images=not args.no_images)
    try:
        listing = fetch_album_listing(downloader.fetcher.session, downloader.output_dir, args.album,
                                      delay=args.delay, jitter=args.jitter, refresh=args.refresh_album)
    except VerificationRequired as e:
        print(f"✗ {e}")
        return 1
    except WeChatError as e:
        print(f"错误: {e}")
        return 1
    name = "／".join(part for part in (listing.nickname, listing.title) if part) or listing.album_id
    print(f"合集：{name}，共 {len(listing.articles)} 篇")
    if listing.article_count > len(listing.articles):
        print(f"! 合集显示有 {listing.article_count} 篇，接口只返回了 {len(listing.articles)} 篇"
              f"（可能有已删除或付费文章），可稍后加 --refresh-album 重试")
    if not listing.articles:
        print("错误: 合集里没有可下载的文章")
        return 1
    print()
    if listing.requests and (args.delay > 0 or args.jitter > 0):
        time.sleep(args.delay + random.uniform(0, args.jitter))
    result = download_url_list(downloader, listing.urls, delay=args.delay, jitter=args.jitter,
                               retry_images=not args.no_retry_images)
    print_summary(result, downloader.output_dir / PROGRESS_FILE)
    return 1 if result.failed or result.partial or result.stopped else 0


if __name__ == '__main__':
    sys.exit(main())
