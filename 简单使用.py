#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章下载工具 - 简单使用版本
只需要输入文章链接，其他都自动完成
"""
import sys
from wechat_downloader.api import WeChatAPI
from wechat_downloader.downloader import ArticleDownloader

def main():
    print("=" * 60)
    print("  微信公众号文章下载工具 - 简单版")
    print("=" * 60)
    print()
    print("💡 提示：直接粘贴文章链接即可，不需要其他设置")
    print()
    
    # 获取文章链接
    article_url = input("请输入文章链接（或按 Ctrl+C 退出）: ").strip()
    
    if not article_url:
        print("❌ 链接不能为空")
        return
    
    print()
    print("⏳ 正在下载，请稍候...")
    print()
    
    # 初始化（不需要token）
    api = WeChatAPI(token=None)
    downloader = ArticleDownloader(output_dir="downloads")
    
    # 获取文章内容
    article_data = api.get_article_content(article_url)
    
    if not article_data:
        print("❌ 下载失败")
        print()
        print("可能的原因：")
        print("  - 网络连接问题")
        print("  - 文章链接无效")
        print("  - 微信公众号的反爬虫机制")
        return
    
    # 获取公众号信息
    account_info = api.get_account_info(article_url)
    account_name = account_info['account_name'] if account_info else ""
    
    # 下载文章
    file_path = downloader.download_article(
        article_data,
        account_name=account_name
    )
    
    if file_path:
        print("✅ 下载成功！")
        print()
        print(f"📄 文件位置: {file_path}")
        print()
        print("💡 提示：文件已保存在 downloads/ 文件夹中")
        print("   可以在 Finder 中打开查看")
    else:
        print("❌ 下载失败")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")

