"""
主程序入口
"""
import argparse
import sys
import time
from typing import List, Optional

from .api import WeChatAPI
from .downloader import ArticleDownloader
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
        except WeChatError as e:
            print(f"{prefix}✗ {url}\n    {e}")
            failed += 1
        else:
            print(f"{prefix}✓ {result.article.title}\n    → {result.path}")
            if result.failed_images:
                print(f"    ! {len(result.failed_images)} 张图片下载失败，已保留原始链接：")
                for image_url in result.failed_images:
                    print(f"      {image_url}")
            if result.kept_images:
                print(f"    ! {len(result.kept_images)} 张图片这次下载失败，沿用了上次下载的本地文件：")
                for image_url in result.kept_images:
                    print(f"      {image_url}")
        if index < len(urls) and interval > 0:
            time.sleep(interval)
    return failed


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description='微信公众号文章下载工具：把文章保存为 Markdown，图片下载到本地',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 下载单篇文章（支持 /s/xxx 短链接）
  python -m wechat_downloader.main "https://mp.weixin.qq.com/s/xxx"

  # 一次下载多篇
  python -m wechat_downloader.main URL1 URL2 URL3 -o ~/Documents/公众号

  # 用历史文章接口批量下载（需要从微信客户端抓到的 token，见 README）
  python -m wechat_downloader.main --url URL --token TOKEN --batch --count 10
        """
    )
    parser.add_argument('urls', nargs='*', metavar='URL', help='文章链接，可传多个')
    parser.add_argument('--url', '-u', action='append', default=[], help='文章链接（可重复，兼容旧用法）')
    parser.add_argument('--output', '-o', default='downloads', help='输出目录（默认: downloads）')
    parser.add_argument('--no-images', action='store_true', help='不下载图片，Markdown 里保留微信原始图片链接')
    parser.add_argument('--interval', type=float, default=2.0, help='多篇下载之间的间隔秒数（默认: 2）')
    parser.add_argument('--token', '-t', help='历史文章接口 token（仅 --batch 使用）')
    parser.add_argument('--token-clipboard', action='store_true', help='从剪贴板读取token')
    parser.add_argument('--batch', '-b', action='store_true', help='通过历史文章接口批量下载该公众号文章（需要 token）')
    parser.add_argument('--count', '-c', type=int, default=10, help='批量下载数量（默认: 10）')
    parser.add_argument('--offset', type=int, default=0, help='起始偏移量（默认: 0）')

    args = parser.parse_args(argv)
    urls = args.urls + args.url
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


if __name__ == '__main__':
    sys.exit(main())
