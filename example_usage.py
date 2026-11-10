#!/usr/bin/env python3
"""
使用示例脚本
"""
import sys
from wechat_downloader.api import WeChatAPI
from wechat_downloader.batch import PROGRESS_FILE, download_url_list, print_summary, read_url_file
from wechat_downloader.downloader import ArticleDownloader


def example_single_article():
    """示例：下载单篇文章（无需token）"""
    print("=" * 50)
    print("示例：下载单篇文章（无需token）")
    print("=" * 50)

    article_url = input("请输入文章URL: ").strip()
    if not article_url:
        print("错误: URL不能为空")
        return

    # 初始化（无需token）
    api = WeChatAPI()
    downloader = ArticleDownloader(output_dir="downloads")

    # 获取公众号信息
    print("\n正在获取公众号信息...")
    account_info = api.get_account_info(article_url)
    account_name = account_info['account_name'] if account_info else ""

    # 获取文章内容
    print("正在获取文章内容...")
    article_data = api.get_article_content(article_url)

    if not article_data:
        print("错误: 无法获取文章内容")
        return

    print(f"标题: {article_data['title']}")
    print(f"作者: {article_data.get('author', '未知')}")

    # 下载文章
    print("\n正在下载...")
    file_path = downloader.download_article(article_data, account_name=account_name)

    if file_path:
        print(f"\n✓ 下载完成: {file_path}")
    else:
        print("\n✗ 下载失败")


def example_batch_download():
    """示例：按链接清单批量下载（无需token，支持断点续传）"""
    print("=" * 50)
    print("示例：按链接清单批量下载（无需token）")
    print("=" * 50)

    links_file = input("请输入链接清单文件路径（每行一个文章链接）: ").strip()
    if not links_file:
        print("错误: 路径不能为空")
        return

    try:
        urls = read_url_file(links_file)
    except OSError as e:
        print(f"错误: 无法读取 {links_file}：{e}")
        return
    if not urls:
        print("错误: 文件里没有文章链接")
        return

    downloader = ArticleDownloader(output_dir="downloads")
    result = download_url_list(downloader, urls, delay=3, jitter=2)
    print_summary(result, downloader.output_dir / PROGRESS_FILE)


def main():
    """主函数"""
    print("\n微信公众号文章下载工具 - 无需token，无需证书\n")
    print("1. 下载单篇文章")
    print("2. 按链接清单批量下载")
    print("3. 退出")

    choice = input("\n请选择 (1-3): ").strip()

    if choice == "1":
        example_single_article()
    elif choice == "2":
        example_batch_download()
    elif choice == "3":
        print("再见！")
        sys.exit(0)
    else:
        print("无效选择")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




