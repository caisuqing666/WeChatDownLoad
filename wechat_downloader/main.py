"""
主程序入口
"""
import sys
import argparse
from pathlib import Path
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
        description='微信公众号文章批量下载工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 下载单篇文章
  python -m wechat_downloader.main --url "https://mp.weixin.qq.com/s/xxx" --token "your_token"
  
  # 批量下载公众号文章
  python -m wechat_downloader.main --url "https://mp.weixin.qq.com/s/xxx" --token "your_token" --batch --count 10
  
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
    
    # 获取token
    token = args.token
    if args.token_clipboard:
        token = get_token_from_clipboard()
        if not token:
            print("错误: 无法从剪贴板读取token")
            sys.exit(1)
    
    if not token:
        print("错误: 需要提供token")
        print("提示: 在微信中打开文章链接，从浏览器开发者工具中获取token")
        print("      或者使用 --token-clipboard 从剪贴板读取")
        sys.exit(1)
    
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
    
    if args.batch:
        # 批量下载
        print(f"\n开始批量下载，数量: {args.count}...")
        articles = api.get_article_list(
            account_info['biz_id'],
            offset=args.offset,
            count=args.count
        )
        
        if not articles:
            print("错误: 无法获取文章列表，请检查token是否有效")
            sys.exit(1)
        
        print(f"找到 {len(articles)} 篇文章")
        
        for idx, article in enumerate(articles, 1):
            print(f"\n[{idx}/{len(articles)}] 正在下载: {article['title']}")
            
            # 获取文章详细内容
            article_data = api.get_article_content(article['link'])
            if article_data:
                file_path = downloader.download_article(
                    article_data,
                    account_name=account_info['account_name']
                )
                if file_path:
                    print(f"✓ 已保存: {file_path}")
                else:
                    print("✗ 下载失败")
            else:
                print("✗ 无法获取文章内容")
    else:
        # 下载单篇文章
        print("\n正在下载文章...")
        article_data = api.get_article_content(args.url)
        
        if not article_data:
            print("错误: 无法获取文章内容")
            sys.exit(1)
        
        print(f"标题: {article_data['title']}")
        file_path = downloader.download_article(
            article_data,
            account_name=account_info['account_name']
        )
        
        if file_path:
            print(f"\n✓ 下载完成: {file_path}")
        else:
            print("\n✗ 下载失败")


if __name__ == '__main__':
    main()




