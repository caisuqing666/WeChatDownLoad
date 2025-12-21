"""
微信公众号API接口封装
"""
import re
import json
import time
import requests
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs


class WeChatAPI:
    """微信公众号API客户端"""
    
    BASE_URL = "https://mp.weixin.qq.com"
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化API客户端
        
        Args:
            token: 微信公众号访问token（从微信浏览器中获取）
        """
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def extract_biz_id(self, article_url: str) -> Optional[str]:
        """
        从文章URL中提取公众号ID (__biz)
        
        Args:
            article_url: 微信公众号文章链接
            
        Returns:
            公众号ID，如果提取失败返回None
        """
        try:
            parsed = urlparse(article_url)
            params = parse_qs(parsed.query)
            biz_id = params.get('__biz', [None])[0]
            return biz_id
        except Exception as e:
            print(f"提取公众号ID失败: {e}")
            return None
    
    def get_account_info(self, article_url: str) -> Optional[Dict]:
        """
        获取公众号信息
        
        Args:
            article_url: 文章URL
            
        Returns:
            包含公众号信息的字典
        """
        biz_id = self.extract_biz_id(article_url)
        if not biz_id:
            return None
        
        # 访问文章页面获取公众号信息
        try:
            response = self.session.get(article_url, timeout=10)
            response.raise_for_status()
            
            # 从HTML中提取公众号名称
            html = response.text
            account_name_match = re.search(r'var\s+nickname\s*=\s*["\']([^"\']+)["\']', html)
            account_name = account_name_match.group(1) if account_name_match else "未知公众号"
            
            return {
                'biz_id': biz_id,
                'account_name': account_name,
                'article_url': article_url
            }
        except Exception as e:
            print(f"获取公众号信息失败: {e}")
            return None
    
    def get_article_list_simple(self, article_url: str, max_count: int = 20) -> List[Dict]:
        """
        无需token，通过网页解析获取文章列表（简化版）

        Args:
            article_url: 任意一篇文章URL（用于获取公众号信息）
            max_count: 最大获取数量

        Returns:
            文章列表
        """
        biz_id = self.extract_biz_id(article_url)
        if not biz_id:
            print("无法提取公众号ID")
            return []

        # 访问公众号主页
        profile_url = f"{self.BASE_URL}/mp/profile_ext?action=home&__biz={biz_id}"

        try:
            response = self.session.get(profile_url, timeout=15)
            response.raise_for_status()
            html = response.text

            # 从HTML中提取文章链接
            articles = []
            found_urls = set()

            # 方法1: 提取所有/s/链接
            url_pattern = r'https?://mp\.weixin\.qq\.com/s/[a-zA-Z0-9_-]+'
            urls = re.findall(url_pattern, html)

            for url in urls:
                base_url = url.split('?')[0]
                if base_url not in found_urls and len(articles) < max_count:
                    found_urls.add(base_url)

                    # 添加biz参数
                    full_url = f"{base_url}?__biz={biz_id}" if '?' not in url else url

                    articles.append({
                        'title': f'文章 {len(articles) + 1}',
                        'link': full_url,
                        'author': ''
                    })

            # 方法2: 尝试提取标题（可选）
            try:
                # 匹配文章数据结构
                data_pattern = r'"content_url":"([^"]+)"[^}]*"title":"([^"]+)"'
                matches = re.findall(data_pattern, html)

                for idx, (url, title) in enumerate(matches):
                    if len(articles) >= max_count:
                        break
                    url = url.replace('\\/', '/')
                    base_url = url.split('?')[0] if '?' in url else url

                    if base_url not in found_urls:
                        found_urls.add(base_url)
                        full_url = f"{base_url}?__biz={biz_id}" if '?' not in url else url

                        # 解码title
                        try:
                            title = title.encode('utf-8').decode('unicode_escape')
                        except:
                            pass

                        if idx < len(articles):
                            articles[idx]['title'] = title
                        else:
                            articles.append({
                                'title': title,
                                'link': full_url,
                                'author': ''
                            })
            except Exception as e:
                print(f"提取标题失败: {e}")

            print(f"从网页中找到 {len(articles)} 篇文章")
            return articles

        except Exception as e:
            print(f"获取文章列表失败: {e}")
            return []

    def get_article_list(self, biz_id: str, offset: int = 0, count: int = 10) -> List[Dict]:
        """
        获取公众号文章列表（需要token的旧方法，保留向后兼容）

        Args:
            biz_id: 公众号ID
            offset: 偏移量
            count: 每页数量

        Returns:
            文章列表
        """
        if not self.token:
            print("⚠️ 提示: 使用get_article_list_simple()方法可以无需token获取文章列表")
            return []

        url = f"{self.BASE_URL}/mp/profile_ext"
        params = {
            'action': 'getmsg',
            '__biz': biz_id,
            'offset': offset,
            'count': count,
            'is_ok': 1,
            'scene': 124,
            'uin': 777,
            'key': 777,
            'pass_ticket': self.token,
            'wxtoken': '',
            'appmsg_token': self.token,
            'x5': 0,
            'f': 'json'
        }

        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get('ret') == 0:
                articles = []
                msg_list = data.get('general_msg_list', '{}')
                if isinstance(msg_list, str):
                    msg_list = json.loads(msg_list)

                for item in msg_list.get('list', []):
                    app_msg = item.get('app_msg_ext_info', {})
                    if app_msg:
                        articles.append({
                            'title': app_msg.get('title', ''),
                            'link': app_msg.get('content_url', ''),
                            'cover': app_msg.get('cover', ''),
                            'digest': app_msg.get('digest', ''),
                            'create_time': app_msg.get('create_time', 0),
                            'author': app_msg.get('author', ''),
                        })

                    # 处理多图文消息
                    for sub_item in app_msg.get('multi_app_msg_item_list', []):
                        articles.append({
                            'title': sub_item.get('title', ''),
                            'link': sub_item.get('content_url', ''),
                            'cover': sub_item.get('cover', ''),
                            'digest': sub_item.get('digest', ''),
                            'create_time': sub_item.get('create_time', 0),
                            'author': sub_item.get('author', ''),
                        })

                return articles
            else:
                print(f"获取文章列表失败: {data.get('errmsg', '未知错误')}")
                return []
        except Exception as e:
            print(f"获取文章列表异常: {e}")
            return []
    
    def get_article_content(self, article_url: str) -> Optional[Dict]:
        """
        获取单篇文章的详细内容
        
        Args:
            article_url: 文章URL
            
        Returns:
            包含文章内容的字典
        """
        # 确保URL完整
        if not article_url.startswith('http'):
            article_url = f"{self.BASE_URL}{article_url}"
        
        try:
            response = self.session.get(article_url, timeout=15)
            response.raise_for_status()
            html = response.text
            
            # 提取文章内容 - 尝试多种方式
            content = None
            
            # 方式1: 从HTML中提取js_content区域（最可靠）
            # 匹配 <div id="js_content" ...>...</div>，需要找到对应的结束标签
            js_content_pattern = r'<div[^>]*id=["\']js_content["\'][^>]*>(.*?)</div>\s*(?=<script|<style|</body>|$)'
            content_match = re.search(js_content_pattern, html, re.DOTALL | re.IGNORECASE)
            if content_match:
                content = content_match.group(1)
                # 清理script和style标签
                content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
            
            # 方式2: 尝试从rich_media_content类提取
            if not content:
                rich_content_pattern = r'<div[^>]*class=["\'][^"\']*rich_media_content[^"\']*["\'][^>]*>(.*?)</div>\s*(?=<script|<style|</body>|$)'
                content_match = re.search(rich_content_pattern, html, re.DOTALL | re.IGNORECASE)
                if content_match:
                    content = content_match.group(1)
                    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
            
            # 方式3: 从JavaScript变量中提取（作为后备）
            if not content:
                content_match = re.search(r'var\s+msg_content\s*=\s*"([^"]+)"', html)
                if content_match:
                    content = content_match.group(1)
                    # 解码HTML实体
                    content = content.replace('\\"', '"').replace('\\/', '/').replace('\\n', '\n')
                    # 处理Unicode转义
                    try:
                        content = content.encode('utf-8').decode('unicode_escape')
                    except:
                        pass
            
            # 如果仍然没有内容，尝试更宽松的提取方式
            if not content or len(content.strip()) < 50:
                # 尝试提取body标签内的所有文本内容（最后手段）
                body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
                if body_match:
                    body_content = body_match.group(1)
                    # 移除所有script和style标签
                    body_content = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    body_content = re.sub(r'<style[^>]*>.*?</style>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
                    # 尝试找到包含中文的段落
                    chinese_paragraphs = re.findall(r'<p[^>]*>([^<]*[\u4e00-\u9fa5]+[^<]*)</p>', body_content, re.IGNORECASE)
                    if chinese_paragraphs:
                        content = '\n'.join(chinese_paragraphs[:50])  # 最多取50段
                
                if not content or len(content.strip()) < 50:
                    print("⚠️  警告: 无法提取文章正文内容，可能遇到反爬虫限制")
                    content = ""
            
            # 提取标题 - 多种方法
            title = "未知标题"
            
            # 方法1: 从JavaScript变量中提取
            title_match = re.search(r'var\s+msg_title\s*=\s*"([^"]+)"', html)
            if title_match:
                title = title_match.group(1).replace('\\"', '"').replace('\\/', '/')
                try:
                    title = title.encode('utf-8').decode('unicode_escape')
                except:
                    pass
            
            # 方法2: 从HTML标题标签提取
            if title == "未知标题":
                title_match = re.search(r'<h1[^>]*class="rich_media_title"[^>]*>(.*?)</h1>', html, re.DOTALL)
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            
            # 方法3: 从activity-name ID提取
            if title == "未知标题":
                title_match = re.search(r'<h1[^>]*id="activity-name"[^>]*>(.*?)</h1>', html, re.DOTALL)
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            
            # 方法4: 从页面title标签提取
            if title == "未知标题":
                title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL)
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                    # 清理title中的额外信息
                    title = title.split('|')[0].split('-')[0].strip()
            
            # 方法5: 从meta标签提取
            if title == "未知标题":
                title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
                if title_match:
                    title = title_match.group(1).strip()
            
            # 提取作者
            author = ""
            author_match = re.search(r'var\s+msg_author\s*=\s*"([^"]+)"', html)
            if author_match:
                author = author_match.group(1).replace('\\"', '"')
                try:
                    author = author.encode('utf-8').decode('unicode_escape')
                except:
                    pass
            else:
                # 尝试从HTML中提取
                author_match = re.search(r'<strong[^>]*class="profile_nickname"[^>]*>(.*?)</strong>', html)
                if author_match:
                    author = re.sub(r'<[^>]+>', '', author_match.group(1)).strip()
            
            # 提取发布时间
            publish_time = 0
            publish_time_match = re.search(r'var\s+ct\s*=\s*(\d+)', html)
            if publish_time_match:
                publish_time = int(publish_time_match.group(1))
            
            return {
                'title': title,
                'author': author,
                'content': content,
                'publish_time': publish_time,
                'url': article_url
            }
        except Exception as e:
            print(f"获取文章内容失败: {e}")
            return None

