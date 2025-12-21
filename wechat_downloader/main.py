"""
主程序入口
"""
import sys
import argparse
from typing import Optional
from .api import WeChatAPI
from .downloader import ArticleDownloader


def get_token_from_clipboard() -> Optional[str]:
    """
    从剪贴板获取token（需要用户手动复制）
    
    Returns:
        token字符串
    """
    try:
        import pyperclip
        return pyperclip.paste().strip()
    except ImportError:
        print("提示: 安装 pyperclip 可以自动从剪贴板读取token")
        print("     运行: pip install pyperclip")
        return None
    except Exception:
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='微信公众号文章批量下载工具（默认无需token）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 下载单篇文章（无需token）
  python -m wechat_downloader.main --url "https://mp.weixin.qq.com/s/xxx"
  
  # 批量下载公众号文章（无需token）
  python -m wechat_downloader.main --url "https://mp.weixin.qq.com/s/xxx" --batch --count 10
  
  # 也可以提供token，优先使用接口方式
  python -m wechat_downloader.main --url "https://mp.weixin.qq.com/s/xxx" --token "your_token" --batch
  
  # 从剪贴板获取token
  python -m wechat_downloader.main --url "https://mp.weixin.qq.com/s/xxx" --token-clipboard
        """
    )
    
    parser.add_argument('--url', '-u', required=True, help='微信公众号文章链接')
    parser.add_argument('--token', '-t', help='访问token（从微信浏览器中获取）')
    parser.add_argument('--token-clipboard', action='store_true', help='从剪贴板读取token')
    parser.add_argument('--output', '-o', default='downloads', help='输出目录（默认: downloads）')
    parser.add_argument('--batch', '-b', action='store_true', help='批量下载公众号文章')
    parser.add_argument('--count', '-c', type=int, default=10, help='批量下载数量（默认: 10）')
    parser.add_argument('--offset', type=int, default=0, help='起始偏移量（默认: 0）')
    
    args = parser.parse_args()
    
    # 获取token（可选）
    token = args.token
    if args.token_clipboard:
        clipboard_token = get_token_from_clipboard()
        if clipboard_token:
            token = clipboard_token
        else:
            print("⚠️ 警告: 无法从剪贴板读取token，将继续使用无需token模式")

    if not token and args.batch:
        print("提示: 未提供token，将使用网页解析模式获取文章列表")

    # 初始化API和下载器
    api = WeChatAPI(token=token)
    downloader = ArticleDownloader(output_dir=args.output)
    
    # 获取公众号信息
    print("正在获取公众号信息...")
    account_info = api.get_account_info(args.url)
    if not account_info:
        print("错误: 无法获取公众号信息，请检查URL是否正确")
        sys.exit(1)
    
    print(f"公众号: {account_info['account_name']}")
    print(f"公众号ID: {account_info['biz_id']}")
    
    def download_and_save(article_url: str):
        """下载文章并保存到磁盘"""
        article_data = api.get_article_content(article_url)
        if not article_data:
            return None
        return downloader.download_article(
            article_data,
            account_name=account_info['account_name']
        )
    
    if args.batch:
        # 批量下载
        total = max(args.count, 0)
        print(f"\n开始批量下载，数量: {total}...")
        articles = []
        
        if token:
            articles = api.get_article_list(
                account_info['biz_id'],
                offset=max(args.offset, 0),
                count=total or 10
            )
            if not articles:
                print("⚠️ 提示: token接口获取文章列表失败，尝试网页解析模式...")
        
        if not articles:
            simple_limit = max(total + max(args.offset, 0), total or 1)
            articles = api.get_article_list_simple(args.url, max_count=simple_limit or 1)
            start = max(args.offset, 0)
            if start:
                articles = articles[start:]
            if total:
                articles = articles[:total]
        
        if not articles:
            print("错误: 无法获取文章列表")
            sys.exit(1)
        
        print(f"找到 {len(articles)} 篇文章")
        
        for idx, article in enumerate(articles, 1):
            print(f"\n[{idx}/{len(articles)}] 正在下载: {article['title']}")
            file_path = download_and_save(article['link'])
            if file_path:
                print(f"✓ 已保存: {file_path}")
            else:
                print("✗ 无法获取文章内容")
    else:
        # 下载单篇文章
        print("\n正在下载文章...")
        file_path = download_and_save(args.url)
        
        if not file_path:
            print("错误: 无法获取文章内容")
            sys.exit(1)
        
        print(f"\n✓ 下载完成: {file_path}")


if __name__ == '__main__':
    main()




