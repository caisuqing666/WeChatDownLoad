/**
 * Content Script - 在微信公众号文章页面中运行
 * 用于提取文章内容和相关信息
 */

(function() {
    'use strict';

    // 等待页面加载完成
    function waitForElement(selector, timeout = 10000) {
        return new Promise((resolve, reject) => {
            const element = document.querySelector(selector);
            if (element) {
                resolve(element);
                return;
            }

            const observer = new MutationObserver((mutations, obs) => {
                const element = document.querySelector(selector);
                if (element) {
                    obs.disconnect();
                    resolve(element);
                }
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true
            });

            setTimeout(() => {
                observer.disconnect();
                reject(new Error(`Element ${selector} not found`));
            }, timeout);
        });
    }

    // 提取文章信息
    function extractArticleInfo() {
        try {
            // 提取标题
            const titleElement = document.querySelector('#activity-name') || 
                                document.querySelector('h1.rich_media_title') ||
                                document.querySelector('h1');
            const title = titleElement ? titleElement.textContent.trim() : '未知标题';

            // 提取作者
            const authorElement = document.querySelector('#meta_content .rich_media_meta_text') ||
                                 document.querySelector('.profile_nickname') ||
                                 document.querySelector('#meta_content strong');
            const author = authorElement ? authorElement.textContent.trim() : '';

            // 提取发布时间
            const timeElement = document.querySelector('#publish_time') ||
                              document.querySelector('.publish_time');
            const publishTime = timeElement ? timeElement.textContent.trim() : '';

            // 提取公众号名称
            const accountElement = document.querySelector('#meta_content .profile_nickname') ||
                                 document.querySelector('#js_name') ||
                                 document.querySelector('.profile_nickname');
            const accountName = accountElement ? accountElement.textContent.trim() : '';

            // 提取文章内容
            const contentElement = document.querySelector('#js_content') ||
                                  document.querySelector('.rich_media_content');
            
            if (!contentElement) {
                throw new Error('无法找到文章内容区域');
            }

            // 提取封面图
            const coverImg = document.querySelector('#js_article .rich_media_cover img') ||
                           document.querySelector('.rich_media_cover img');
            const coverUrl = coverImg ? coverImg.src : '';

            // 获取当前URL
            const url = window.location.href;

            // 提取公众号ID (__biz)
            const urlParams = new URLSearchParams(window.location.search);
            const bizId = urlParams.get('__biz') || '';

            return {
                title,
                author,
                publishTime,
                accountName,
                content: contentElement,
                coverUrl,
                url,
                bizId
            };
        } catch (error) {
            console.error('提取文章信息失败:', error);
            return null;
        }
    }

    // 将HTML内容转换为Markdown
    function htmlToMarkdown(element) {
        if (!element) return '';

        // 克隆元素以避免修改原DOM
        const clone = element.cloneNode(true);

        // 处理图片
        const images = clone.querySelectorAll('img');
        images.forEach(img => {
            const src = img.src || img.getAttribute('data-src') || '';
            const alt = img.alt || '';
            const markdown = `![${alt}](${src})`;
            const p = document.createElement('p');
            p.textContent = markdown;
            img.parentNode.replaceChild(p, img);
        });

        // 处理链接
        const links = clone.querySelectorAll('a');
        links.forEach(link => {
            const href = link.href || '';
            const text = link.textContent.trim();
            if (href && text) {
                const markdown = `[${text}](${href})`;
                link.textContent = markdown;
                link.removeAttribute('href');
            }
        });

        // 处理标题
        for (let i = 1; i <= 6; i++) {
            const headings = clone.querySelectorAll(`h${i}`);
            headings.forEach(heading => {
                const text = heading.textContent.trim();
                const prefix = '#'.repeat(i);
                heading.textContent = `${prefix} ${text}`;
            });
        }

        // 处理粗体和斜体
        const strongs = clone.querySelectorAll('strong, b');
        strongs.forEach(strong => {
            const text = strong.textContent.trim();
            strong.textContent = `**${text}**`;
        });

        const ems = clone.querySelectorAll('em, i');
        ems.forEach(em => {
            const text = em.textContent.trim();
            em.textContent = `*${text}*`;
        });

        // 处理代码块
        const codeBlocks = clone.querySelectorAll('pre code');
        codeBlocks.forEach(code => {
            const text = code.textContent;
            code.textContent = `\`\`\`\n${text}\n\`\`\``;
        });

        const inlineCodes = clone.querySelectorAll('code:not(pre code)');
        inlineCodes.forEach(code => {
            const text = code.textContent.trim();
            code.textContent = `\`${text}\``;
        });

        // 处理列表
        const lists = clone.querySelectorAll('ul, ol');
        lists.forEach(list => {
            const items = list.querySelectorAll('li');
            items.forEach((item, index) => {
                const text = item.textContent.trim();
                const prefix = list.tagName === 'OL' ? `${index + 1}. ` : '- ';
                item.textContent = `${prefix}${text}`;
            });
        });

        // 处理段落
        const paragraphs = clone.querySelectorAll('p');
        paragraphs.forEach(p => {
            if (p.textContent.trim()) {
                p.textContent = p.textContent.trim() + '\n';
            }
        });

        // 移除所有HTML标签，获取纯文本
        const text = clone.textContent || clone.innerText || '';

        // 清理多余空行
        return text.split('\n')
            .map(line => line.trim())
            .filter(line => line.length > 0)
            .join('\n\n');
    }

    // 提取所有图片URL
    function extractImages(element) {
        const images = element.querySelectorAll('img');
        const imageUrls = [];
        
        images.forEach(img => {
            const src = img.src || img.getAttribute('data-src') || '';
            if (src && src.startsWith('http')) {
                imageUrls.push({
                    url: src,
                    alt: img.alt || ''
                });
            }
        });

        return imageUrls;
    }

    // 监听来自popup的消息
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === 'extractArticle') {
            try {
                const info = extractArticleInfo();
                if (!info) {
                    sendResponse({ success: false, error: '无法提取文章信息' });
                    return;
                }

                const markdown = htmlToMarkdown(info.content);
                const images = extractImages(info.content);

                sendResponse({
                    success: true,
                    data: {
                        title: info.title,
                        author: info.author,
                        publishTime: info.publishTime,
                        accountName: info.accountName,
                        markdown,
                        images,
                        coverUrl: info.coverUrl,
                        url: info.url,
                        bizId: info.bizId
                    }
                });
            } catch (error) {
                sendResponse({ success: false, error: error.message });
            }
            return true; // 保持消息通道开放
        }

        if (request.action === 'checkPage') {
            const isArticlePage = window.location.href.includes('mp.weixin.qq.com/s/');
            sendResponse({ isArticlePage });
            return true;
        }
    });

    // 页面加载完成后，在控制台输出提示
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            console.log('微信公众号文章下载器已加载');
        });
    } else {
        console.log('微信公众号文章下载器已加载');
    }
})();

