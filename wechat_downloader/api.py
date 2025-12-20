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
    
    def get_article_list(self, biz_id: str, offset: int = 0, count: int = 10) -> List[Dict]:
        """
        获取公众号文章列表
        
        Args:
            biz_id: 公众号ID
            offset: 偏移量
            count: 每页数量
            
        Returns:
            文章列表
        """
        if not self.token:
            raise ValueError("需要提供token才能获取文章列表")
        
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
            
            # 方式1: 从变量中提取
            content_match = re.search(r'var\s+msg_content\s*=\s*"([^"]+)"', html)
            if content_match:
                content = content_match.group(1)
                # 解码HTML实体
                content = content.replace('\\"', '"').replace('\\/', '/')
                # 处理Unicode转义
                try:
                    content = content.encode('utf-8').decode('unicode_escape')
                except:
                    pass
            
            # 方式2: 从HTML中提取内容区域
            if not content:
                content_match = re.search(r'id="js_content"[^>]*>(.*?)</div>', html, re.DOTALL)
                if content_match:
                    content = content_match.group(1)
            
            # 方式3: 使用整个HTML作为后备
            if not content:
                content = html
            
            # 提取标题
            title = "未知标题"
            title_match = re.search(r'var\s+msg_title\s*=\s*"([^"]+)"', html)
            if title_match:
                title = title_match.group(1).replace('\\"', '"')
                try:
                    title = title.encode('utf-8').decode('unicode_escape')
                except:
                    pass
            else:
                # 尝试从HTML标题标签提取
                title_match = re.search(r'<h1[^>]*class="rich_media_title"[^>]*>(.*?)</h1>', html, re.DOTALL)
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            
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

