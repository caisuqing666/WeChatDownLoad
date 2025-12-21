#!/usr/bin/env python3
"""
微信公众号文章下载并合并为PDF工具 - Mac版
支持单篇/多篇下载（无需token）和批量下载（需要token）
"""
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import re

from wechat_downloader.api import WeChatAPI
from wechat_downloader.downloader import ArticleDownloader

try:
    from markdown import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    markdown = None

# 尝试导入PDF引擎
PDF_AVAILABLE = False
PDF_ENGINE = None

# 优先尝试 weasyprint
try:
    from weasyprint import HTML, CSS
    PDF_AVAILABLE = True
    PDF_ENGINE = 'weasyprint'
except (ImportError, OSError):
    # weasyprint 不可用，尝试 reportlab
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        PDF_AVAILABLE = True
        PDF_ENGINE = 'reportlab'
    except ImportError:
        PDF_AVAILABLE = False
        PDF_ENGINE = None

if not PDF_AVAILABLE:
    print("⚠️  警告: PDF功能需要安装额外依赖")
    print("   运行: pip install markdown reportlab")
    print("   或: pip install markdown weasyprint (需要系统依赖)")


class PDFMerger:
    """PDF合并器"""
    
    def __init__(self):
        self.pdf_available = PDF_AVAILABLE
        self.pdf_engine = PDF_ENGINE
    
    def markdown_to_html(self, markdown_content: str, title: str = "", author: str = "") -> str:
        """将Markdown转换为HTML"""
        html_content = markdown(markdown_content, extensions=['extra', 'codehilite'])
        
        # 创建完整的HTML文档
        html_doc = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            line-height: 1.8;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
            color: #333;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 30px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        h3 {{
            color: #555;
        }}
        p {{
            margin: 15px 0;
            text-align: justify;
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px auto;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "Courier New", monospace;
        }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        blockquote {{
            border-left: 4px solid #3498db;
            padding-left: 20px;
            margin: 20px 0;
            color: #666;
            font-style: italic;
        }}
        hr {{
            border: none;
            border-top: 2px solid #eee;
            margin: 40px 0;
        }}
        .article-header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #eee;
        }}
        .article-title {{
            font-size: 28px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .article-author {{
            color: #7f8c8d;
            font-size: 16px;
        }}
    </style>
</head>
<body>
    <div class="article-header">
        <div class="article-title">{title}</div>
        {f'<div class="article-author">作者: {author}</div>' if author else ''}
    </div>
    {html_content}
</body>
</html>"""
        return html_doc
    
    def html_to_pdf(self, html_content: str, output_path: Path) -> bool:
        """将HTML转换为PDF"""
        if not self.pdf_available:
            print("❌ PDF功能不可用，请安装: pip install markdown reportlab")
            return False
        
        try:
            if self.pdf_engine == 'weasyprint':
                html = HTML(string=html_content)
                html.write_pdf(output_path)
                return True
            elif self.pdf_engine == 'reportlab':
                return self._markdown_to_pdf_reportlab(html_content, output_path)
            else:
                return False
        except Exception as e:
            print(f"❌ PDF生成失败: {e}")
            return False
    
    def _markdown_to_pdf_reportlab(self, markdown_content: str, output_path: Path) -> bool:
        """使用reportlab将Markdown转换为PDF"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib.enums import TA_LEFT, TA_CENTER
            import re
            
            # 创建PDF文档
            doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                                  rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=18)
            
            # 样式
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor='#2c3e50',
                spaceAfter=30,
                alignment=TA_LEFT
            )
            
            # 解析Markdown（简化版）
            story = []
            
            # 移除front matter
            if markdown_content.startswith('---'):
                parts = markdown_content.split('---', 2)
                if len(parts) >= 3:
                    markdown_content = parts[2].strip()
            
            # 按行处理
            lines = markdown_content.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 0.2*inch))
                    continue
                
                # 标题
                if line.startswith('#'):
                    level = len(line) - len(line.lstrip('#'))
                    text = line.lstrip('# ').strip()
                    if level == 1:
                        story.append(Paragraph(text, title_style))
                    else:
                        story.append(Paragraph(text, styles[f'Heading{min(level, 6)}']))
                    story.append(Spacer(1, 0.2*inch))
                # 粗体
                elif '**' in line or '__' in line:
                    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
                    story.append(Paragraph(text, styles['Normal']))
                    story.append(Spacer(1, 0.1*inch))
                # 普通段落
                else:
                    # 转义HTML特殊字符
                    text = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(text, styles['Normal']))
                    story.append(Spacer(1, 0.1*inch))
            
            # 构建PDF
            doc.build(story)
            return True
        except Exception as e:
            print(f"❌ ReportLab PDF生成失败: {e}")
            return False
    
    def merge_pdfs(self, pdf_files: List[Path], output_path: Path) -> bool:
        """合并多个PDF文件"""
        if not self.pdf_available:
            return False
        
        try:
            from PyPDF2 import PdfMerger
            merger = PdfMerger()
            
            for pdf_file in pdf_files:
                if pdf_file.exists():
                    merger.append(str(pdf_file))
            
            merger.write(str(output_path))
            merger.close()
            return True
        except ImportError:
            # 如果没有PyPDF2，使用weasyprint直接合并HTML
            return self._merge_via_html(pdf_files, output_path)
        except Exception as e:
            print(f"❌ PDF合并失败: {e}")
            return False
    
    def _merge_via_html(self, pdf_files: List[Path], output_path: Path) -> bool:
        """通过HTML方式合并（备用方案）"""
        # 读取所有PDF的HTML内容并合并
        # 这是一个简化的实现
        return False


def download_multiple_articles(urls: List[str], account_name: str = "", pdf_filename: str = "") -> bool:
    """下载多篇文章并合并为PDF"""
    print("\n" + "=" * 50)
    print(f"开始下载 {len(urls)} 篇文章...")
    print("=" * 50)
    
    # 初始化
    api = WeChatAPI(token=None)
    downloader = ArticleDownloader(output_dir="downloads")
    pdf_merger = PDFMerger()
    
    if not pdf_merger.pdf_available:
        print("\n⚠️  PDF功能需要安装依赖:")
        print("   pip install markdown weasyprint PyPDF2")
        print("\n将只下载Markdown格式文件")
        download_pdf = False
    else:
        download_pdf = True
    
    # 存储文章数据
    articles_data = []
    pdf_files = []
    
    # 下载每篇文章
    for idx, url in enumerate(urls, 1):
        print(f"\n[{idx}/{len(urls)}]")
        print("正在下载...")
        
        # 获取文章内容
        article_data = api.get_article_content(url)
        if not article_data:
            print(f"  ✗ 无法获取文章内容")
            continue
        
        title = article_data.get('title', f'文章{idx}')
        author = article_data.get('author', '')
        
        print(f"√ {title}")
        
        # 下载Markdown
        md_file = downloader.download_article(article_data, account_name=account_name)
        if md_file:
            articles_data.append({
                'title': title,
                'author': author,
                'content': article_data.get('content', ''),
                'markdown_file': md_file
            })
            
            # 如果支持PDF，生成PDF
            if download_pdf:
                try:
                    # 读取Markdown内容
                    with open(md_file, 'r', encoding='utf-8') as f:
                        md_content = f.read()
                        # 移除front matter
                        if md_content.startswith('---'):
                            parts = md_content.split('---', 2)
                            if len(parts) >= 3:
                                md_content = parts[2].strip()
                    
                    # 生成PDF
                    pdf_file = md_file.with_suffix('.pdf')
                    if pdf_merger.pdf_engine == 'reportlab':
                        # 使用reportlab直接处理markdown
                        if pdf_merger._markdown_to_pdf_reportlab(md_content, pdf_file):
                            pdf_files.append(pdf_file)
                            print(f"  ✓ PDF已生成")
                    else:
                        # 使用weasyprint需要先转HTML
                        html_content = pdf_merger.markdown_to_html(md_content, title, author)
                        if pdf_merger.html_to_pdf(html_content, pdf_file):
                            pdf_files.append(pdf_file)
                            print(f"  ✓ PDF已生成")
                except Exception as e:
                    print(f"  ⚠️  PDF生成失败: {e}")
    
    # 合并PDF
    if download_pdf and pdf_files and len(pdf_files) > 1:
        print(f"\n正在合并 {len(pdf_files)} 个PDF文件...")
        
        # 确定输出文件名
        if not pdf_filename:
            pdf_filename = f"{account_name or 'articles'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 清理文件名
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', pdf_filename)
        output_pdf = Path("downloads") / f"{safe_filename}.pdf"
        
        if pdf_merger.merge_pdfs(pdf_files, output_pdf):
            print(f"✓ 合并完成: {output_pdf}")
            
            # 删除临时PDF文件（可选）
            # for pdf_file in pdf_files:
            #     pdf_file.unlink()
        else:
            print("⚠️  PDF合并失败，但单个PDF文件已保存")
    
    print("\n" + "=" * 50)
    print("✅ 下载完成！")
    print("=" * 50)
    
    return True


def batch_download_with_token(article_url: str, token: str, count: int = 20):
    """批量下载（需要token）"""
    print("=" * 50)
    print("批量下载模式（需要token）")
    print("=" * 50)
    
    api = WeChatAPI(token=token)
    downloader = ArticleDownloader(output_dir="downloads")
    
    # 获取公众号信息
    print("\n正在获取公众号信息...")
    account_info = api.get_account_info(article_url)
    if not account_info:
        print("错误: 无法获取公众号信息")
        return
    
    print(f"公众号: {account_info['account_name']}")
    print(f"公众号ID: {account_info['biz_id']}")
    
    # 获取文章列表
    print(f"\n正在获取文章列表（数量: {count}）...")
    articles = api.get_article_list(account_info['biz_id'], offset=0, count=count)
    
    if not articles:
        print("⚠️  token接口获取失败，尝试网页解析模式...")
        articles = api.get_article_list_simple(article_url, max_count=count)
    
    if not articles:
        print("错误: 无法获取文章列表")
        return
    
    print(f"找到 {len(articles)} 篇文章\n")
    
    # 下载每篇文章
    for idx, article in enumerate(articles, 1):
        print(f"[{idx}/{len(articles)}] {article['title']}")
        
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
    print("\n" + "=" * 50)
    print("微信公众号文章下载并合并为PDF工具 - Mac版")
    print("=" * 50)
    print()
    print("请选择下载模式:")
    print("1. 单篇/多篇下载 (提供文章链接,无需token)")
    print("2. 批量下载 (需要token,可下载历史所有文章)")
    print()
    
    choice = input("请选择模式 (1/2): ").strip()
    
    if choice == "1":
        print("\n" + "=" * 50)
        print("单篇/多篇下载模式")
        print("=" * 50)
        print()
        print("请输入文章链接(每行一个,输入空行结束):")
        print("示例: https://mp.weixin.qq.com/s/xxxxX")
        print()
        
        urls = []
        while True:
            url = input().strip()
            if not url:
                break
            if url.startswith('http') and 'mp.weixin.qq.com' in url:
                urls.append(url)
            elif url:
                print(f"⚠️  跳过无效URL: {url}")
        
        if not urls:
            print("错误: 没有输入有效的文章链接")
            return
        
        print(f"已输入 {len(urls)} 篇文章")
        print("(按回车,输入空行结束)")
        
        # 输入公众号名称
        account_name = input("\n请输入公众号名称(用于PDF封面): ").strip()
        
        # 输入PDF文件名
        pdf_filename = input("PDF文件名(不含扩展名,回车使用默认): ").strip()
        
        # 开始下载
        download_multiple_articles(urls, account_name, pdf_filename)
        
    elif choice == "2":
        print("\n" + "=" * 50)
        print("批量下载模式")
        print("=" * 50)
        print()
        print("⚠️  批量下载需要token")
        print("提示: 单篇下载（模式1）不需要token，可以先测试单篇下载功能")
        
        article_url = input("请输入任意一篇文章URL: ").strip()
        if not article_url:
            print("错误: URL不能为空")
            return
        
        token = input("请输入token: ").strip()
        if not token:
            print("错误: 批量下载需要token")
            return
        
        try:
            count = int(input("请输入下载数量 (默认20): ").strip() or "20")
        except ValueError:
            count = 20
        
        batch_download_with_token(article_url, token, count)
        
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

