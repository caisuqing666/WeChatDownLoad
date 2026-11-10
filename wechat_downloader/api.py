"""
微信公众号API接口封装
"""
import re
import json
import time
import requests
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

from .fetch import Fetcher, WeChatError
from .parse import parse_article


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
        self.fetcher = Fetcher()
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
        获取公众号信息（公众号 ID 从页面读取，支持不带 __biz 的短链接）

        Args:
            article_url: 文章URL

        Returns:
            包含公众号信息的字典
        """
        try:
            article = parse_article(self.fetcher.get_article_html(article_url), article_url)
        except WeChatError as e:
            print(f"获取公众号信息失败: {e}")
            return None
        return {
            'biz_id': article.biz,
            'account_name': article.account_name or "未知公众号",
            'article_url': article_url,
        }

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
        if not article_url.startswith('http'):
            article_url = f"{self.BASE_URL}{article_url}"
        try:
            article = parse_article(self.fetcher.get_article_html(article_url), article_url)
        except WeChatError as e:
            print(f"获取文章内容失败: {e}")
            return None
        return article.to_dict()
