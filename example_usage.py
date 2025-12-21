#!/usr/bin/env python3
"""
使用示例脚本
"""
import sys
from wechat_downloader.api import WeChatAPI
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
    """示例：批量下载公众号文章（无需token）"""
    print("=" * 50)
    print("示例：批量下载公众号文章（无需token）")
    print("=" * 50)

    article_url = input("请输入公众号任意一篇文章URL: ").strip()
    if not article_url:
        print("错误: URL不能为空")
        return

    # 下载数量
    try:
        count = int(input("请输入下载数量 (默认20): ").strip() or "20")
    except ValueError:
        count = 20

    # 初始化（无需token）
    api = WeChatAPI()
    downloader = ArticleDownloader(output_dir="downloads")

    # 获取公众号信息
    print("\n正在获取公众号信息...")
    account_info = api.get_account_info(article_url)
    if not account_info:
        print("错误: 无法获取公众号信息")
        return

    print(f"公众号: {account_info['account_name']}")
    print(f"公众号ID: {account_info['biz_id']}")

    # 使用新的无token方法获取文章列表
    print(f"\n正在获取文章列表（数量: {count}）...")
    articles = api.get_article_list_simple(article_url, max_count=count)

    if not articles:
        print("错误: 无法获取文章列表")
        return

    print(f"找到 {len(articles)} 篇文章\n")

    # 下载每篇文章
    for idx, article in enumerate(articles, 1):
        print(f"[{idx}/{len(articles)}] {article['title']}")

        # 获取详细内容
        article_data = api.get_article_content(article['link'])
        if article_data:
            file_path = downloader.download_article(
                article_data,
                account_name=account_info['account_name']
            )
            if file_path:
                print(f"  ✓ 已保存")
            else:
                print(f"  ✗ 下载失败")
        else:
            print(f"  ✗ 无法获取内容")
        print()

    print("批量下载完成！")


def main():
    """主函数"""
    print("\n微信公众号文章下载工具 - 无需token，无需证书\n")
    print("1. 下载单篇文章")
    print("2. 批量下载公众号文章")
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




