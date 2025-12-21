"""
文章内容下载和解析模块
"""
import re
import os
import requests
from typing import Dict, List, Optional
from pathlib import Path
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser


class HTMLContentExtractor(HTMLParser):
    """HTML内容提取器"""
    
    def __init__(self):
        super().__init__()
        self.content = []
        self.current_tag = None
        self.in_content = False
        
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag == 'div' and ('id', 'js_content') in attrs:
            self.in_content = True
    
    def handle_endtag(self, tag):
        if tag == 'div' and self.in_content:
            self.in_content = False
        self.current_tag = None
    
    def handle_data(self, data):
        if self.in_content:
            self.content.append(data.strip())


class ArticleDownloader:
    """文章下载器"""
    
    def __init__(self, output_dir: str = "downloads"):
        """
        初始化下载器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def download_file(self, url: str, filepath: Path) -> bool:
        """
        下载文件
        
        Args:
            url: 文件URL
            filepath: 保存路径
            
        Returns:
            是否成功
        """
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"下载文件失败 {url}: {e}")
            return False
    
    def extract_images(self, html_content: str) -> List[str]:
        """
        从HTML中提取图片URL
        
        Args:
            html_content: HTML内容
            
        Returns:
            图片URL列表
        """
        # 匹配各种图片格式
        patterns = [
            r'<img[^>]+src=["\']([^"\']+)["\']',
            r'data-src=["\']([^"\']+)["\']',
            r'https?://mmbiz\.qpic\.cn/[^\s"\'<>]+',
        ]
        
        images = []
        for pattern in patterns:
            matches = re.findall(pattern, html_content)
            images.extend(matches)
        
        # 去重并过滤
        images = list(set(images))
        images = [img for img in images if img.startswith('http')]
        
        return images
    
    def extract_videos(self, html_content: str) -> List[str]:
        """
        从HTML中提取视频URL
        
        Args:
            html_content: HTML内容
            
        Returns:
            视频URL列表
        """
        patterns = [
            r'<video[^>]+src=["\']([^"\']+)["\']',
            r'data-src=["\']([^"\']+)["\']',
            r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*',
        ]
        
        videos = []
        for pattern in patterns:
            matches = re.findall(pattern, html_content)
            videos.extend(matches)
        
        return list(set(videos))
    
    def clean_html_to_text(self, html: str) -> str:
        """
        将HTML转换为纯文本
        
        Args:
            html: HTML内容
            
        Returns:
            纯文本内容
        """
        # 移除script和style标签
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 替换常见HTML标签
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<p[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</p>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<div[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</div>', '', html, flags=re.IGNORECASE)
        
        # 移除所有HTML标签
        html = re.sub(r'<[^>]+>', '', html)
        
        # 解码HTML实体
        import html as html_module
        html = html_module.unescape(html)
        
        # 清理空白
        lines = [line.strip() for line in html.split('\n')]
        lines = [line for line in lines if line]
        
        return '\n'.join(lines)
    
    def html_to_markdown(self, html: str, base_url: str = "") -> str:
        """
        将HTML转换为Markdown格式
        
        Args:
            html: HTML内容
            base_url: 基础URL，用于处理相对路径
            
        Returns:
            Markdown格式的内容
        """
        # 首先清理script和style标签（防止乱码）
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除JavaScript代码块
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 提取标题
        title_match = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html, re.IGNORECASE | re.DOTALL)
        
        # 转换图片
        def replace_img(match):
            src = match.group(1)
            alt = match.group(2) if match.group(2) else ""
            if not src.startswith('http'):
                src = urljoin(base_url, src)
            return f"![{alt}]({src})"
        
        html = re.sub(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\']', replace_img, html)
        html = re.sub(r'<img[^>]+alt=["\']([^"\']*)["\'][^>]+src=["\']([^"\']+)["\']', replace_img, html)
        html = re.sub(r'<img[^>]+src=["\']([^"\']+)["\']', replace_img, html)
        
        # 转换链接
        def replace_link(match):
            href = match.group(1)
            text = match.group(2)
            if not href.startswith('http'):
                href = urljoin(base_url, href)
            return f"[{text}]({href})"
        
        html = re.sub(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', replace_link, html, flags=re.DOTALL)
        
        # 转换标题
        for i in range(1, 7):
            html = re.sub(f'<h{i}[^>]*>(.*?)</h{i}>', lambda m: f"{'#' * i} {m.group(1).strip()}\n", html, flags=re.IGNORECASE | re.DOTALL)
        
        # 转换粗体
        html = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 转换斜体
        html = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 转换代码块
        html = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', r'```\n\1\n```', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除其他标签（保留换行）
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<p[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</p>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<div[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</div>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<[^>]+>', '', html)
        
        # 解码HTML实体
        import html as html_module
        html = html_module.unescape(html)
        
        # 清理空白和空行
        lines = [line.strip() for line in html.split('\n')]
        lines = [line for line in lines if line and not line.startswith('var ') and not line.startswith('function')]
        
        # 移除JavaScript代码残留和CSS样式
        cleaned_lines = []
        skip = False
        in_script = False
        in_style = False
        
        for line in lines:
            # 跳过JavaScript代码块
            if any(keyword in line for keyword in ['() =>', '=> {', 'function(', 'const ', 'var ', 'let ', 'document.', 'window.', 'navigator.', 'setTimeout', 'addEventListener']):
                skip = True
                continue
            if skip and ('});' in line or line.strip() == '}' or line.strip().endswith(');')):
                skip = False
                continue
            
            # 跳过CSS样式代码
            if '{--weui-' in line or '--weui-BG' in line or '--weui-FG' in line or '@media' in line:
                continue
            if '.wx-root' in line or '.weui-' in line or 'body,' in line:
                continue
            
            # 跳过HTML标签残留
            if line.strip().startswith('<') and line.strip().endswith('>'):
                continue
            
            # 跳过过长的行（通常是压缩的CSS/JS）
            if len(line) > 500:
                continue
            
            # 跳过只有标点符号的行
            if line.strip() in ['：', '，', '。', '&nbsp;', '']:
                continue
            
            if not skip:
                cleaned_lines.append(line)
        
        # 进一步清理：移除重复的空行
        result = '\n'.join(cleaned_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()
    
    def download_article(self, article_data: Dict, account_name: str = "", download_images: bool = False) -> Optional[Path]:
        """
        下载单篇文章（简化版）

        Args:
            article_data: 文章数据字典
            account_name: 公众号名称
            download_images: 是否下载图片

        Returns:
            保存的文件路径
        """
        title = article_data.get('title', '未命名文章')
        content = article_data.get('content', '')
        url = article_data.get('url', '')

        # 清理文件名
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:100]

        # 创建输出目录
        output_path = self.output_dir / account_name if account_name else self.output_dir
        output_path.mkdir(parents=True, exist_ok=True)

        # 转换为Markdown
        markdown_content = self.html_to_markdown(content, url)

        # 下载图片（可选）
        if download_images:
            images = self.extract_images(content)
            if images:
                img_dir = output_path / f"{safe_title}_images"
                img_dir.mkdir(exist_ok=True)

                for idx, img_url in enumerate(images[:20]):
                    try:
                        ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
                        img_file = img_dir / f"image_{idx+1}{ext}"
                        if self.download_file(img_url, img_file):
                            markdown_content = markdown_content.replace(
                                img_url, f"{safe_title}_images/image_{idx+1}{ext}"
                            )
                    except:
                        pass

        # 生成最终内容
        final_content = f"""---
title: {title}
author: {article_data.get('author', '')}
url: {url}
publish_time: {article_data.get('publish_time', 0)}
---

{markdown_content}
"""

        # 保存文件
        md_file = output_path / f"{safe_title}.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(final_content)

        return md_file





