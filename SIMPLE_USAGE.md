# 微信公众号文章下载工具 - 简洁使用指南

## ✨ 特点

- ✅ **无需安装证书**
- ✅ **无需token**（批量下载也不需要！）
- ✅ **代码简洁**（核心代码不到50行）
- ✅ **支持批量下载**

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests
```

### 2. 运行示例程序

```bash
python example_usage.py
```

### 3. 选择功能

**选项1：下载单篇文章**
- 输入文章URL
- 自动下载为Markdown格式

**选项2：批量下载公众号文章**
- 输入公众号任意一篇文章URL
- 输入要下载的数量（默认20篇）
- 自动批量下载所有文章

## 📝 代码示例

### 下载单篇文章

```python
from wechat_downloader.api import WeChatAPI
from wechat_downloader.downloader import ArticleDownloader

# 初始化（无需token）
api = WeChatAPI()
downloader = ArticleDownloader(output_dir="downloads")

# 下载文章
article_url = "https://mp.weixin.qq.com/s/xxxxx"
article_data = api.get_article_content(article_url)
file_path = downloader.download_article(article_data)

print(f"下载完成: {file_path}")
```

### 批量下载公众号文章

```python
from wechat_downloader.api import WeChatAPI
from wechat_downloader.downloader import ArticleDownloader

# 初始化（无需token）
api = WeChatAPI()
downloader = ArticleDownloader(output_dir="downloads")

# 获取公众号信息
article_url = "https://mp.weixin.qq.com/s/xxxxx"
account_info = api.get_account_info(article_url)

# 获取文章列表（无需token）
articles = api.get_article_list_simple(article_url, max_count=20)

# 批量下载
for article in articles:
    article_data = api.get_article_content(article['link'])
    downloader.download_article(article_data, account_name=account_info['account_name'])

print("批量下载完成！")
```

## 🎯 核心API

### WeChatAPI

- `get_account_info(article_url)` - 获取公众号信息
- `get_article_content(article_url)` - 获取单篇文章内容
- `get_article_list_simple(article_url, max_count)` - **新增！无需token获取文章列表**

### ArticleDownloader

- `download_article(article_data, account_name, download_images)` - 下载文章

## 🔧 优化内容

1. **新增 `get_article_list_simple()` 方法**
   - 通过网页解析获取文章列表
   - 完全无需token
   - 代码简洁高效

2. **简化 `download_article()` 方法**
   - 减少重复代码
   - 图片下载改为可选参数
   - 更清晰的代码结构

3. **更新使用示例**
   - 移除所有token相关代码
   - 更简洁的使用方式
   - 更友好的提示信息

## 📂 输出格式

下载的文章保存为Markdown格式，包含：

```markdown
---
title: 文章标题
author: 作者
url: 原文链接
publish_time: 发布时间
---

文章内容（Markdown格式）
```

## ⚠️ 注意事项

1. 批量下载时，文章数量取决于公众号主页可见的文章数
2. 部分需要登录的公众号可能无法获取完整文章列表
3. 建议添加适当的延迟，避免请求过快

## 🆚 对比

### 之前：
- ❌ 批量下载需要token
- ❌ 需要从微信浏览器手动获取token
- ❌ 代码复杂，难以理解

### 现在：
- ✅ 完全无需token
- ✅ 只需提供文章URL
- ✅ 代码简洁，易于使用

## 📞 技术原理

通过访问公众号主页，从HTML中提取文章链接列表，而不是调用需要认证的API接口。这种方式：

- 不需要任何认证信息
- 不需要安装证书
- 代码更简单
- 更容易维护
