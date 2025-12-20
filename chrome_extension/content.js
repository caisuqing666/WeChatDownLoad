/**
 * Content Script - 在微信公众号文章页面中运行
 * 用于提取文章内容和元数据
 */

(function() {
    'use strict';

    // 存储提取的数据
    window.wechatArticleData = null;

    /**
     * 提取文章数据
     */
    function extractArticleData() {
        try {
            const data = {
                title: '',
                author: '',
                publishTime: '',
                content: '',
                images: [],
                bizId: '',
                articleUrl: window.location.href,
                token: null
            };

            // 提取标题
            const titleElement = document.querySelector('#activity-name, .rich_media_title, h1');
            if (titleElement) {
                data.title = titleElement.textContent.trim();
            } else {
                // 尝试从 JavaScript 变量中提取
                const titleMatch = document.documentElement.innerHTML.match(/var\s+msg_title\s*=\s*"([^"]+)"/);
                if (titleMatch) {
                    data.title = titleMatch[1].replace(/\\"/g, '"').replace(/\\\//g, '/');
                    try {
                        data.title = JSON.parse('"' + data.title + '"');
                    } catch (e) {
                        // 如果解析失败，使用原始值
                    }
                }
            }

            // 提取作者
            const authorElement = document.querySelector('#meta_content .rich_media_meta_text, .profile_nickname, #author');
            if (authorElement) {
                data.author = authorElement.textContent.trim();
            } else {
                const authorMatch = document.documentElement.innerHTML.match(/var\s+msg_author\s*=\s*"([^"]+)"/);
                if (authorMatch) {
                    data.author = authorMatch[1].replace(/\\"/g, '"');
                    try {
                        data.author = JSON.parse('"' + data.author + '"');
                    } catch (e) {
                        // 如果解析失败，使用原始值
                    }
                }
            }

            // 提取发布时间
            const timeElement = document.querySelector('#publish_time, .publish_time, em#post-date');
            if (timeElement) {
                data.publishTime = timeElement.textContent.trim();
            } else {
                const timeMatch = document.documentElement.innerHTML.match(/var\s+ct\s*=\s*(\d+)/);
                if (timeMatch) {
                    const timestamp = parseInt(timeMatch[1]) * 1000;
                    data.publishTime = new Date(timestamp).toLocaleString('zh-CN');
                }
            }

            // 提取公众号ID
            const urlParams = new URLSearchParams(window.location.search);
            data.bizId = urlParams.get('__biz') || '';

            // 提取文章内容
            const contentElement = document.querySelector('#js_content, .rich_media_content');
            if (contentElement) {
                data.content = contentElement.innerHTML;
            } else {
                // 尝试从 JavaScript 变量中提取
                const contentMatch = document.documentElement.innerHTML.match(/var\s+msg_content\s*=\s*"([^"]+)"/);
                if (contentMatch) {
                    let content = contentMatch[1];
                    content = content.replace(/\\"/g, '"').replace(/\\\//g, '/').replace(/\\n/g, '\n');
                    try {
                        content = JSON.parse('"' + content + '"');
                    } catch (e) {
                        // 如果解析失败，使用原始值
                    }
                    data.content = content;
                }
            }

            // 提取所有图片
            const images = [];
            const imgElements = document.querySelectorAll('#js_content img, .rich_media_content img');
            imgElements.forEach((img, index) => {
                let src = img.getAttribute('src') || img.getAttribute('data-src') || '';
                if (src && !src.startsWith('data:')) {
                    // 处理相对路径
                    if (src.startsWith('//')) {
                        src = 'https:' + src;
                    } else if (src.startsWith('/')) {
                        src = window.location.origin + src;
                    }
                    images.push({
                        url: src,
                        alt: img.getAttribute('alt') || `图片${index + 1}`,
                        index: index
                    });
                }
            });
            data.images = images;

            // 尝试提取 token（从页面变量或 cookie）
            try {
                // 从 cookie 中获取
                const cookies = document.cookie.split(';');
                for (let cookie of cookies) {
                    const [name, value] = cookie.trim().split('=');
                    if (name === 'appmsg_token' || name === 'pass_ticket') {
                        data.token = value;
                        break;
                    }
                }
            } catch (e) {
                console.log('无法提取 token:', e);
            }

            return data;
        } catch (error) {
            console.error('提取文章数据失败:', error);
            return null;
        }
    }

    /**
     * 监听来自 popup 的消息
     */
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        console.log('收到消息:', request);
        
        if (request.action === 'extract') {
            const data = extractArticleData();
            window.wechatArticleData = data;
            console.log('提取的文章数据:', data);
            sendResponse({ success: true, data: data });
        } else if (request.action === 'getData') {
            sendResponse({ success: true, data: window.wechatArticleData });
        }
        return true; // 保持消息通道开放
    });

    // 页面加载完成后自动提取
    function initExtraction() {
        window.wechatArticleData = extractArticleData();
        console.log('文章数据已提取:', window.wechatArticleData);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initExtraction);
    } else {
        // 如果页面已经加载，立即提取
        initExtraction();
    }

    // 监听页面变化（单页应用可能动态加载内容）
    const observer = new MutationObserver(() => {
        if (!window.wechatArticleData || !window.wechatArticleData.title) {
            initExtraction();
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    console.log('微信公众号文章下载器已加载');
})();
