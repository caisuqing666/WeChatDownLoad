"""
微信公众号API接口封装
"""
import json
import requests
from typing import Dict, List, Optional

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
            print("⚠️ 提示: 历史文章接口需要从微信客户端抓到的 token")
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
