# 微信公众号文章下载工具 - 简洁使用指南

## ✨ 特点

- ✅ **无需安装证书**
- ✅ **无需token**（按链接清单批量下载也不需要）
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

**选项2：按链接清单批量下载**
- 准备一个文本文件，每行一个文章链接（空行和 # 开头的注释会被忽略）
- 输入文件路径，逐篇下载；已下载的自动跳过，中断后重新运行会接着下

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

### 按链接清单批量下载

```python
from wechat_downloader.batch import download_url_list, read_url_file
from wechat_downloader.downloader import ArticleDownloader

downloader = ArticleDownloader(output_dir="downloads")
urls = read_url_file("links.txt")  # 每行一个链接，忽略空行和 # 注释，自动去重
result = download_url_list(downloader, urls, delay=3, jitter=2)
print(f"新下载 {result.downloaded} 篇，跳过 {result.skipped} 篇，失败 {len(result.failed)} 篇")
```

命令行等价写法：`python -m wechat_downloader.main --urls links.txt`

## 🎯 核心API

### WeChatAPI

- `get_account_info(article_url)` - 获取公众号信息
- `get_article_content(article_url)` - 获取单篇文章内容

### ArticleDownloader

- `download_article(article_data, account_name, download_images)` - 下载文章

## 🔧 优化内容

1. **按链接清单批量下载（`wechat_downloader.batch`）**
   - 用户自己整理文章链接，逐篇下载
   - 限速 + 随机抖动，遇到验证页立即停止
   - 断点续传，已下载的自动跳过

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

1. 不登录无法自动获取某个公众号的历史文章列表，批量下载需要自己整理链接
2. 请保留默认的请求间隔，请求过快会触发“环境异常”验证页
