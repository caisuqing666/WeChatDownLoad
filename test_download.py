#!/usr/bin/env python3
"""
自动测试脚本 - 测试单篇文章下载功能
"""
import sys
from wechat_downloader.api import WeChatAPI
from wechat_downloader.downloader import ArticleDownloader

def test_single_article():
    """测试单篇文章下载（免token）"""
    print("=" * 60)
    print("微信公众号文章下载工具 - 功能测试")
    print("=" * 60)
    print()
    
    # 使用您微信中的文章URL
    test_url = "https://mp.weixin.qq.com/s/ey_Klj1Ih4KCiBa-k3FU8w"
    
    print(f"测试文章URL: {test_url}")
    print()
    
    # 初始化（不需要token）
    print("1. 初始化API和下载器...")
    api = WeChatAPI(token=None)  # 免token
    downloader = ArticleDownloader(output_dir="downloads")
    print("   ✓ 初始化成功")
    print()
    
    # 获取公众号信息
    print("2. 获取公众号信息...")
    account_info = api.get_account_info(test_url)
    if account_info:
        print(f"   ✓ 公众号: {account_info['account_name']}")
        print(f"   ✓ 公众号ID: {account_info['biz_id']}")
        account_name = account_info['account_name']
    else:
        print("   ⚠️ 无法获取公众号信息，继续测试...")
        account_name = ""
    print()
    
    # 获取文章内容
    print("3. 获取文章内容...")
    article_data = api.get_article_content(test_url)
    
    if not article_data:
        print("   ✗ 无法获取文章内容")
        print()
        print("可能的原因：")
        print("  - 网络连接问题")
        print("  - 文章URL无效或已过期")
        print("  - 微信公众号的反爬虫机制")
        return False
    
    print(f"   ✓ 标题: {article_data['title']}")
    print(f"   ✓ 作者: {article_data.get('author', '未知')}")
    print(f"   ✓ 内容长度: {len(article_data.get('content', ''))} 字符")
    print(f"   ✓ 图片数量: {len(article_data.get('images', []))}")
    print()
    
    # 下载文章
    print("4. 下载文章...")
    try:
        file_path = downloader.download_article(
            article_data,
            account_name=account_name
        )
        
        if file_path:
            print(f"   ✓ 下载成功！")
            print(f"   ✓ 文件位置: {file_path}")
            print()
            print("=" * 60)
            print("✅ 测试完成！文章已保存到 downloads/ 文件夹")
            print("=" * 60)
            return True
        else:
            print("   ✗ 下载失败")
            return False
    except Exception as e:
        print(f"   ✗ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = test_single_article()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


