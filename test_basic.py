#!/usr/bin/env python3
"""
基本功能测试脚本
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    try:
        from wechat_downloader.api import WeChatAPI
        from wechat_downloader.downloader import ArticleDownloader
        print("✓ 模块导入成功")
        return True
    except Exception as e:
        print(f"✗ 模块导入失败: {e}")
        return False

def test_api_init():
    """测试API初始化"""
    print("\n测试API初始化...")
    try:
        from wechat_downloader.api import WeChatAPI
        api = WeChatAPI()
        print("✓ API初始化成功")
        return True
    except Exception as e:
        print(f"✗ API初始化失败: {e}")
        return False

def test_extract_biz_id():
    """测试公众号ID提取"""
    print("\n测试公众号ID提取...")
    try:
        from wechat_downloader.api import WeChatAPI
        api = WeChatAPI()
        
        test_url = "https://mp.weixin.qq.com/s?__biz=MzI4NjAxNjY4Nw==&mid=2650241901"
        biz_id = api.extract_biz_id(test_url)
        
        if biz_id == "MzI4NjAxNjY4Nw==":
            print(f"✓ 公众号ID提取成功: {biz_id}")
            return True
        else:
            print(f"✗ 公众号ID提取失败，期望: MzI4NjAxNjY4Nw==, 实际: {biz_id}")
            return False
    except Exception as e:
        print(f"✗ 公众号ID提取异常: {e}")
        return False

def test_downloader_init():
    """测试下载器初始化"""
    print("\n测试下载器初始化...")
    try:
        from wechat_downloader.downloader import ArticleDownloader
        downloader = ArticleDownloader(output_dir="test_downloads")
        print("✓ 下载器初始化成功")
        return True
    except Exception as e:
        print(f"✗ 下载器初始化失败: {e}")
        return False

def test_html_to_markdown():
    """测试HTML转Markdown"""
    print("\n测试HTML转Markdown...")
    try:
        from wechat_downloader.downloader import ArticleDownloader
        downloader = ArticleDownloader()
        
        test_html = '<h1>标题</h1><p>这是<strong>粗体</strong>文本</p><img src="test.jpg" alt="测试">'
        markdown = downloader.html_to_markdown(test_html)
        
        if markdown and len(markdown) > 0:
            print(f"✓ HTML转Markdown成功")
            print(f"  示例输出: {markdown[:50]}...")
            return True
        else:
            print("✗ HTML转Markdown失败，输出为空")
            return False
    except Exception as e:
        print(f"✗ HTML转Markdown异常: {e}")
        return False

def main():
    """运行所有测试"""
    print("=" * 50)
    print("微信公众号下载工具 - 基本功能测试")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_api_init,
        test_extract_biz_id,
        test_downloader_init,
        test_html_to_markdown,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ 测试异常: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("✓ 所有测试通过！")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())




