/**
 * Batch Content Script - 在微信公众号文章列表页面中运行
 * 用于提取文章列表和批量下载
 */

(function() {
    'use strict';

    // 存储文章列表
    window.wechatArticleList = [];

    /**
     * 提取文章列表
     */
    function extractArticleList() {
        const articles = [];
        
        try {
            // 方法1: 从消息列表页面提取
            const msgItems = document.querySelectorAll('.msg_item, .weui_media_box, [class*="msg"], [class*="article"]');
            
            msgItems.forEach((item, index) => {
                try {
                    // 查找文章链接
                    const linkElement = item.querySelector('a[href*="/s/"]');
                    if (!linkElement) return;
                    
                    const href = linkElement.getAttribute('href');
                    if (!href || !href.includes('/s/')) return;
                    
                    // 构建完整URL
                    let articleUrl = href;
                    if (href.startsWith('/')) {
                        articleUrl = 'https://mp.weixin.qq.com' + href;
                    } else if (href.startsWith('//')) {
                        articleUrl = 'https:' + href;
                    }
                    
                    // 提取标题
                    const titleElement = item.querySelector('.weui_media_title, .msg_title, h4, h3, [class*="title"]');
                    const title = titleElement ? titleElement.textContent.trim() : `文章 ${index + 1}`;
                    
                    // 提取时间
                    const timeElement = item.querySelector('.weui_media_extra_info, .msg_time, [class*="time"], em');
                    const time = timeElement ? timeElement.textContent.trim() : '';
                    
                    // 提取摘要
                    const descElement = item.querySelector('.weui_media_desc, .msg_desc, [class*="desc"], p');
                    const desc = descElement ? descElement.textContent.trim() : '';
                    
                    articles.push({
                        url: articleUrl,
                        title: title,
                        time: time,
                        description: desc,
                        index: index
                    });
                } catch (e) {
                    console.error('提取文章项失败:', e);
                }
            });

            // 方法2: 如果方法1没找到，尝试从页面中查找所有文章链接
            if (articles.length === 0) {
                const allLinks = document.querySelectorAll('a[href*="/s/"]');
                allLinks.forEach((link, index) => {
                    const href = link.getAttribute('href');
                    if (href && href.includes('/s/')) {
                        let articleUrl = href;
                        if (href.startsWith('/')) {
                            articleUrl = 'https://mp.weixin.qq.com' + href;
                        } else if (href.startsWith('//')) {
                            articleUrl = 'https:' + href;
                        }
                        
                        const title = link.textContent.trim() || link.getAttribute('title') || `文章 ${index + 1}`;
                        
                        // 避免重复
                        if (!articles.find(a => a.url === articleUrl)) {
                            articles.push({
                                url: articleUrl,
                                title: title,
                                time: '',
                                description: '',
                                index: articles.length
                            });
                        }
                    }
                });
            }

            // 方法3: 从 JavaScript 变量中提取（如果页面使用动态加载）
            if (articles.length === 0) {
                try {
                    // 尝试从页面脚本中提取
                    const scripts = document.querySelectorAll('script');
                    scripts.forEach(script => {
                        const content = script.textContent;
                        // 查找包含文章链接的脚本
                        const urlMatches = content.match(/https?:\/\/mp\.weixin\.qq\.com\/s\/[a-zA-Z0-9_-]+/g);
                        if (urlMatches) {
                            urlMatches.forEach((url, index) => {
                                if (!articles.find(a => a.url === url)) {
                                    articles.push({
                                        url: url,
                                        title: `文章 ${articles.length + 1}`,
                                        time: '',
                                        description: '',
                                        index: articles.length
                                    });
                                }
                            });
                        }
                    });
                } catch (e) {
                    console.error('从脚本提取失败:', e);
                }
            }

        } catch (error) {
            console.error('提取文章列表失败:', error);
        }

        return articles;
    }

    /**
     * 监听来自 popup 的消息
     */
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === 'getArticleList') {
            const articles = extractArticleList();
            window.wechatArticleList = articles;
            sendResponse({ success: true, articles: articles });
        } else if (request.action === 'scrollToLoadMore') {
            // 滚动加载更多文章
            window.scrollTo(0, document.body.scrollHeight);
            setTimeout(() => {
                const articles = extractArticleList();
                window.wechatArticleList = articles;
                sendResponse({ success: true, articles: articles });
            }, 1000);
        }
        return true;
    });

    // 页面加载完成后自动提取
    function initExtraction() {
        window.wechatArticleList = extractArticleList();
        console.log('文章列表已提取:', window.wechatArticleList.length, '篇文章');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initExtraction);
    } else {
        initExtraction();
    }

    // 监听页面变化（动态加载）
    const observer = new MutationObserver(() => {
        // 延迟提取，避免频繁触发
        clearTimeout(window.extractTimeout);
        window.extractTimeout = setTimeout(() => {
            const newArticles = extractArticleList();
            if (newArticles.length > window.wechatArticleList.length) {
                window.wechatArticleList = newArticles;
                console.log('文章列表已更新:', window.wechatArticleList.length, '篇文章');
            }
        }, 500);
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    console.log('批量下载脚本已加载');
})();

