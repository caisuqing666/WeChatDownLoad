/**
 * Popup Script - 扩展弹窗逻辑
 */

document.addEventListener('DOMContentLoaded', async () => {
    const statusDiv = document.getElementById('status');
    const articleInfoDiv = document.getElementById('articleInfo');
    const articleTitle = document.getElementById('articleTitle');
    const articleAuthor = document.getElementById('articleAuthor');
    const articleTime = document.getElementById('articleTime');
    const imageCount = document.getElementById('imageCount');
    const downloadBtn = document.getElementById('downloadBtn');
    const downloadWithImagesBtn = document.getElementById('downloadWithImagesBtn');
    const formatSelect = document.getElementById('formatSelect');
    const loadingDiv = document.getElementById('loading');
    
    // 批量下载相关元素
    const singleDownloadSection = document.getElementById('singleDownloadSection');
    const batchDownloadSection = document.getElementById('batchDownloadSection');
    const articleList = document.getElementById('articleList');
    const articleCount = document.getElementById('articleCount');
    const selectAllBtn = document.getElementById('selectAllBtn');
    const selectNoneBtn = document.getElementById('selectNoneBtn');
    const batchDownloadBtn = document.getElementById('batchDownloadBtn');
    const batchProgress = document.getElementById('batchProgress');
    const progressText = document.getElementById('progressText');
    const progressBar = document.getElementById('progressBar');
    const pauseBatchBtn = document.getElementById('pauseBatchBtn');
    const cancelBatchBtn = document.getElementById('cancelBatchBtn');
    const footerText = document.getElementById('footerText');

    let articleData = null;
    let articleListData = [];
    let selectedArticles = new Set();
    let isBatchDownloading = false;
    let batchDownloadPaused = false;
    let batchDownloadCancelled = false;
    let currentMode = 'single'; // 'single' 或 'batch'

    // 调试：检查库是否加载
    console.log('扩展程序已加载');
    console.log('html2pdf 库状态:', typeof html2pdf !== 'undefined' ? '已加载' : '未加载');

    /**
     * 更新状态显示
     */
    function updateStatus(message, type = 'info') {
        statusDiv.textContent = message;
        statusDiv.className = `status ${type}`;
    }

    /**
     * 检查当前标签页是否是微信公众号文章页面或列表页面
     */
    async function checkCurrentTab() {
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            
            console.log('当前标签页 URL:', tab.url);
            
            if (!tab.url || !tab.url.includes('mp.weixin.qq.com')) {
                updateStatus('❌ 请在微信公众号页面使用此扩展', 'error');
                return false;
            }

            // 检查是否是文章列表页面
            const isListPage = tab.url.includes('mp.weixin.qq.com/mp/profile_ext') || 
                              tab.url.includes('mp.weixin.qq.com/mp/homepage') ||
                              tab.url.includes('mp.weixin.qq.com/profile');
            
            if (isListPage) {
                // 显示批量下载界面
                singleDownloadSection.style.display = 'none';
                batchDownloadSection.style.display = 'block';
                footerText.textContent = '在公众号文章列表页面，可以批量下载文章';
                // 自动获取文章列表（可选，用户也可以手动点击按钮）
                // await fetchArticleList();
                return true;
            }

            // 检查是否是单篇文章页面
            if (!tab.url.includes('mp.weixin.qq.com/s/')) {
                updateStatus('❌ 请在微信公众号文章页面或文章列表页面使用', 'error');
                return false;
            }

            // 显示单篇下载界面
            singleDownloadSection.style.display = 'block';
            batchDownloadSection.style.display = 'none';
            footerText.textContent = '请确保在微信公众号文章页面使用';

            // 先尝试注入 content script（如果还没有注入）
            try {
                await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    files: ['content.js']
                });
                console.log('Content script 已注入');
            } catch (injectError) {
                console.log('Content script 可能已存在或注入失败:', injectError);
                // 继续尝试，可能已经注入了
            }

            // 等待一下让 content script 初始化
            await new Promise(resolve => setTimeout(resolve, 200));

            // 向 content script 发送消息获取文章数据
            try {
                const response = await chrome.tabs.sendMessage(tab.id, { action: 'extract' });
                console.log('收到响应:', response);
                
                if (response && response.success && response.data) {
                    articleData = response.data;
                    
                    // 检查数据是否有效
                    if (!articleData.title && !articleData.content) {
                        updateStatus('⚠️ 文章内容为空，请等待页面完全加载后重试', 'error');
                        return false;
                    }
                    
                    displayArticleInfo(articleData);
                    updateStatus('✅ 已检测到文章内容', 'success');
                    downloadBtn.disabled = false;
                    downloadWithImagesBtn.disabled = false;
                    return true;
                } else {
                    updateStatus('⚠️ 无法提取文章内容，请刷新页面重试', 'error');
                    console.error('响应数据无效:', response);
                    return false;
                }
            } catch (error) {
                console.error('获取文章数据失败:', error);
                
                // 如果是连接错误，提示用户刷新页面
                if (error.message && error.message.includes('Could not establish connection')) {
                    updateStatus('⚠️ 无法连接到页面，请刷新文章页面后重试', 'error');
                } else {
                    updateStatus('⚠️ 无法获取文章数据: ' + (error.message || '未知错误'), 'error');
                }
                return false;
            }
        } catch (error) {
            console.error('检查标签页失败:', error);
            updateStatus('❌ 发生错误: ' + (error.message || '未知错误'), 'error');
            return false;
        }
    }

    /**
     * 显示文章信息
     */
    function displayArticleInfo(data) {
        articleTitle.textContent = data.title || '未知标题';
        articleAuthor.textContent = data.author || '未知作者';
        articleTime.textContent = data.publishTime || '未知时间';
        imageCount.textContent = data.images ? data.images.length : 0;
        articleInfoDiv.style.display = 'block';
    }

    /**
     * HTML 转 Markdown
     */
    function htmlToMarkdown(html) {
        let md = html;

        // 转换标题
        md = md.replace(/<h([1-6])[^>]*>(.*?)<\/h\1>/gi, (match, level, content) => {
            const text = content.replace(/<[^>]+>/g, '').trim();
            return '\n' + '#'.repeat(parseInt(level)) + ' ' + text + '\n';
        });

        // 转换粗体
        md = md.replace(/<strong[^>]*>(.*?)<\/strong>/gi, '**$1**');
        md = md.replace(/<b[^>]*>(.*?)<\/b>/gi, '**$1**');

        // 转换斜体
        md = md.replace(/<em[^>]*>(.*?)<\/em>/gi, '*$1*');
        md = md.replace(/<i[^>]*>(.*?)<\/i>/gi, '*$1*');

        // 转换链接
        md = md.replace(/<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)<\/a>/gi, '[$2]($1)');

        // 转换图片
        md = md.replace(/<img[^>]+src=["']([^"']+)["'][^>]*alt=["']([^"']*)["'][^>]*>/gi, '![$2]($1)');
        md = md.replace(/<img[^>]+alt=["']([^"']*)["'][^>]+src=["']([^"']+)["'][^>]*>/gi, '![$1]($2)');
        md = md.replace(/<img[^>]+src=["']([^"']+)["'][^>]*>/gi, '![]($1)');

        // 转换代码块
        md = md.replace(/<pre[^>]*><code[^>]*>(.*?)<\/code><\/pre>/gi, '```\n$1\n```');
        md = md.replace(/<code[^>]*>(.*?)<\/code>/gi, '`$1`');

        // 转换列表
        md = md.replace(/<ul[^>]*>/gi, '\n');
        md = md.replace(/<\/ul>/gi, '\n');
        md = md.replace(/<ol[^>]*>/gi, '\n');
        md = md.replace(/<\/ol>/gi, '\n');
        md = md.replace(/<li[^>]*>(.*?)<\/li>/gi, '- $1\n');

        // 转换段落
        md = md.replace(/<p[^>]*>(.*?)<\/p>/gi, '$1\n\n');
        md = md.replace(/<div[^>]*>(.*?)<\/div>/gi, '$1\n');

        // 移除所有剩余 HTML 标签
        md = md.replace(/<[^>]+>/g, '');

        // 解码 HTML 实体
        const textarea = document.createElement('textarea');
        textarea.innerHTML = md;
        md = textarea.value;

        // 清理多余空行
        md = md.replace(/\n{3,}/g, '\n\n');
        md = md.trim();

        return md;
    }

    /**
     * 生成文件内容
     */
    function generateFileContent(data, format, includeImages = false) {
        const title = data.title || '未命名文章';
        const author = data.author || '未知作者';
        const time = data.publishTime || new Date().toLocaleString('zh-CN');
        const url = data.articleUrl || '';

        let content = '';
        let metadata = '';

        if (format === 'markdown') {
            metadata = `---
title: ${title}
author: ${author}
publish_time: ${time}
url: ${url}
---

`;
            content = htmlToMarkdown(data.content);
        } else if (format === 'html' || format === 'pdf') {
            // HTML 和 PDF 使用相同的 HTML 结构
            metadata = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title}</title>
    <style>
        @page { margin: 2cm; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px; 
            line-height: 1.8; 
            color: #333;
        }
        h1 { 
            color: #333; 
            border-bottom: 2px solid #667eea; 
            padding-bottom: 10px; 
            margin-bottom: 20px;
            font-size: 24px;
        }
        h2, h3, h4 {
            color: #444;
            margin-top: 24px;
            margin-bottom: 12px;
        }
        .meta { 
            color: #666; 
            font-size: 14px; 
            margin-bottom: 30px; 
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
        }
        .meta p {
            margin: 5px 0;
        }
        .content {
            font-size: 16px;
        }
        .content p {
            margin: 12px 0;
            text-align: justify;
        }
        img { 
            max-width: 100%; 
            height: auto; 
            display: block;
            margin: 20px auto;
            border-radius: 4px;
        }
        a {
            color: #667eea;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        code {
            background: #f5f5f5;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }
        pre {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            border-left: 3px solid #667eea;
        }
        blockquote {
            border-left: 4px solid #667eea;
            padding-left: 15px;
            margin-left: 0;
            color: #666;
            font-style: italic;
        }
        ul, ol {
            margin: 12px 0;
            padding-left: 30px;
        }
        li {
            margin: 8px 0;
        }
    </style>
</head>
<body>
    <h1>${title}</h1>
    <div class="meta">
        <p><strong>作者:</strong> ${author}</p>
        <p><strong>发布时间:</strong> ${time}</p>
        <p><strong>原文链接:</strong> <a href="${url}">${url}</a></p>
    </div>
    <div class="content">
`;
            content = data.content;
            metadata += content + `
    </div>
</body>
</html>`;
            return metadata;
        } else if (format === 'text') {
            // 纯文本
            const div = document.createElement('div');
            div.innerHTML = data.content;
            content = div.textContent || div.innerText || '';
            metadata = `标题: ${title}\n作者: ${author}\n发布时间: ${time}\n原文链接: ${url}\n\n${'='.repeat(50)}\n\n`;
        }

        return metadata + content;
    }

    /**
     * 等待库加载完成
     */
    function waitForLibrary(libraryName, maxWait = 5000) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            const checkLibrary = () => {
                if (typeof window[libraryName] !== 'undefined') {
                    resolve();
                } else if (Date.now() - startTime > maxWait) {
                    reject(new Error(`库 ${libraryName} 加载超时`));
                } else {
                    setTimeout(checkLibrary, 100);
                }
            };
            checkLibrary();
        });
    }

    /**
     * 生成并下载 PDF
     */
    async function generatePDF(data) {
        return new Promise(async (resolve, reject) => {
            try {
                // 检查库是否加载
                updateStatus('⏳ 正在检查 PDF 库...', 'info');
                
                if (typeof html2pdf === 'undefined') {
                    // 尝试等待库加载
                    try {
                        await waitForLibrary('html2pdf', 2000);
                    } catch (e) {
                        updateStatus('❌ PDF 库未加载，请刷新扩展', 'error');
                        reject(new Error('PDF 库未加载'));
                        return;
                    }
                }

                updateStatus('⏳ 正在准备内容...', 'info');

                // 生成 HTML 内容
                const htmlContent = generateFileContent(data, 'html');
                
                // 创建临时容器（隐藏但可见，用于渲染）
                const container = document.createElement('div');
                container.style.position = 'fixed';
                container.style.left = '0';
                container.style.top = '0';
                container.style.width = '800px';
                container.style.padding = '40px';
                container.style.backgroundColor = 'white';
                container.style.zIndex = '999999';
                container.style.overflow = 'auto';
                container.style.maxHeight = '100vh';
                container.innerHTML = htmlContent;
                document.body.appendChild(container);

                // 等待 DOM 渲染
                await new Promise(resolve => setTimeout(resolve, 500));

                // 等待图片加载（简化版）
                const images = container.querySelectorAll('img');
                if (images.length > 0) {
                    updateStatus(`⏳ 正在加载 ${images.length} 张图片...`, 'info');
                    const imagePromises = Array.from(images).map(img => {
                        if (img.complete) return Promise.resolve();
                        return new Promise((resolve) => {
                            img.onload = resolve;
                            img.onerror = resolve; // 即使失败也继续
                            setTimeout(resolve, 2000); // 超时保护
                        });
                    });
                    await Promise.all(imagePromises);
                }

                updateStatus('📄 正在生成 PDF，请稍候...', 'info');

                // 配置 PDF 选项
                const filename = `${(data.title || '未命名文章').replace(/[<>:"/\\|?*]/g, '_').substring(0, 50)}.pdf`;
                
                const opt = {
                    margin: [10, 10, 10, 10],
                    filename: filename,
                    image: { type: 'jpeg', quality: 0.92 },
                    html2canvas: { 
                        scale: 1.5,
                        useCORS: true,
                        logging: false,
                        letterRendering: true,
                        allowTaint: false,
                        backgroundColor: '#ffffff'
                    },
                    jsPDF: { 
                        unit: 'mm', 
                        format: 'a4', 
                        orientation: 'portrait'
                    }
                };

                // 生成 PDF
                try {
                    await html2pdf()
                        .set(opt)
                        .from(container)
                        .save();
                    
                    updateStatus('✅ PDF 生成成功！', 'success');
                    
                    // 清理
                    setTimeout(() => {
                        if (container.parentNode) {
                            document.body.removeChild(container);
                        }
                    }, 1000);
                    
                    resolve();
                } catch (pdfError) {
                    console.error('PDF 生成错误:', pdfError);
                    updateStatus('❌ PDF 生成失败: ' + (pdfError.message || '未知错误'), 'error');
                    
                    // 清理
                    if (container.parentNode) {
                        document.body.removeChild(container);
                    }
                    
                    reject(pdfError);
                }

            } catch (error) {
                console.error('PDF 生成过程失败:', error);
                updateStatus('❌ 错误: ' + (error.message || '未知错误'), 'error');
                reject(error);
            }
        });
    }

    /**
     * 下载文件
     */
    async function downloadArticle(includeImages = false) {
        if (!articleData) {
            updateStatus('❌ 没有可下载的内容', 'error');
            return;
        }

        try {
            loadingDiv.classList.add('active');
            downloadBtn.disabled = true;
            downloadWithImagesBtn.disabled = true;

            const format = formatSelect.value;
            
            // 如果是 PDF 格式，使用特殊的 PDF 生成方法
            if (format === 'pdf') {
                try {
                    updateStatus('📄 正在生成 PDF...', 'info');
                    await generatePDF(articleData);
                    updateStatus('✅ PDF 下载成功！', 'success');
                    
                    // 如果包含图片，下载图片
                    if (includeImages && articleData.images && articleData.images.length > 0) {
                        updateStatus('📥 正在下载图片...', 'info');
                        const title = (articleData.title || '未命名文章').replace(/[<>:"/\\|?*]/g, '_').substring(0, 50);
                        await downloadImages(title);
                    }
                } catch (pdfError) {
                    // PDF 生成失败，提供备用方案
                    console.error('PDF 生成失败，尝试备用方案:', pdfError);
                    updateStatus('⚠️ PDF 生成失败，使用打印功能...', 'info');
                    
                    // 备用方案：使用打印功能
                    const htmlContent = generateFileContent(articleData, 'html');
                    const printWindow = window.open('', '_blank');
                    if (printWindow) {
                        printWindow.document.write(htmlContent);
                        printWindow.document.close();
                        await new Promise(resolve => setTimeout(resolve, 500));
                        printWindow.print();
                        updateStatus('📄 请在弹出的打印对话框中选择"另存为 PDF"', 'info');
                    } else {
                        throw new Error('无法打开打印窗口，请允许弹窗');
                    }
                }
                return;
            }

            // 其他格式的下载逻辑
            const content = generateFileContent(articleData, format, includeImages);
            
            // 生成文件名
            const title = (articleData.title || '未命名文章').replace(/[<>:"/\\|?*]/g, '_').substring(0, 50);
            const extension = format === 'html' ? 'html' : format === 'markdown' ? 'md' : 'txt';
            const filename = `${title}.${extension}`;

            // 使用 data URL 方式下载（Chrome 扩展中 blob URL 可能不工作）
            const mimeType = format === 'html' ? 'text/html' : format === 'markdown' ? 'text/markdown' : 'text/plain';
            const dataUrl = `data:${mimeType};charset=utf-8,${encodeURIComponent(content)}`;

            // 使用 Chrome downloads API 下载
            const downloadId = await chrome.downloads.download({
                url: dataUrl,
                filename: filename,
                saveAs: true
            });

            // 监听下载完成
            chrome.downloads.onChanged.addListener(function listener(delta) {
                if (delta.id === downloadId) {
                    if (delta.state && delta.state.current === 'complete') {
                        updateStatus('✅ 下载成功！', 'success');
                        chrome.downloads.onChanged.removeListener(listener);
                    } else if (delta.state && delta.state.current === 'interrupted') {
                        updateStatus('❌ 下载被中断', 'error');
                        chrome.downloads.onChanged.removeListener(listener);
                    }
                }
            });

            // 如果 3 秒内没有完成，也显示成功（可能用户选择了保存位置）
            setTimeout(() => {
                updateStatus('✅ 下载已启动！', 'success');
            }, 1000);
            
            // 如果包含图片，下载图片
            if (includeImages && articleData.images && articleData.images.length > 0) {
                updateStatus('📥 正在下载图片...', 'info');
                await downloadImages(title);
            }

        } catch (error) {
            console.error('下载失败:', error);
            const errorMsg = error.message || String(error) || '未知错误';
            updateStatus('❌ 下载失败: ' + errorMsg, 'error');
            
            // 尝试备用下载方法
            if (format !== 'pdf') {
                try {
                    updateStatus('⚠️ 尝试备用下载方法...', 'info');
                    const content = generateFileContent(articleData, format, includeImages);
                    const title = (articleData.title || '未命名文章').replace(/[<>:"/\\|?*]/g, '_').substring(0, 50);
                    const extension = format === 'html' ? 'html' : format === 'markdown' ? 'md' : 'txt';
                    const filename = `${title}.${extension}`;
                    
                    // 备用方法：创建下载链接并自动点击
                    const blob = new Blob([content], { 
                        type: format === 'html' ? 'text/html' : format === 'markdown' ? 'text/markdown' : 'text/plain' 
                    });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    a.style.display = 'none';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    setTimeout(() => URL.revokeObjectURL(url), 1000);
                    
                    updateStatus('✅ 使用备用方法下载成功！', 'success');
                    return;
                } catch (backupError) {
                    console.error('备用下载方法也失败:', backupError);
                }
            }
            
            // 显示详细错误信息（用于调试）
            setTimeout(() => {
                alert('下载失败详情：\n' + errorMsg + '\n\n请检查：\n1. 是否在微信公众号文章页面\n2. 扩展程序是否已正确加载\n3. 查看扩展程序错误日志（右键扩展图标 → 检查弹出内容）\n4. 检查浏览器下载权限设置');
            }, 500);
        } finally {
            loadingDiv.classList.remove('active');
            downloadBtn.disabled = false;
            downloadWithImagesBtn.disabled = false;
        }
    }

    /**
     * 下载图片
     */
    async function downloadImages(articleTitle) {
        if (!articleData.images || articleData.images.length === 0) {
            return;
        }

        const imageFolder = articleTitle + '_images';
        
        for (let i = 0; i < Math.min(articleData.images.length, 20); i++) {
            const image = articleData.images[i];
            try {
                const extension = image.url.match(/\.(jpg|jpeg|png|gif|webp)/i)?.[1] || 'jpg';
                const filename = `${imageFolder}/image_${i + 1}.${extension}`;
                
                await chrome.downloads.download({
                    url: image.url,
                    filename: filename,
                    conflictAction: 'uniquify'
                });
                
                // 添加延迟避免请求过快
                await new Promise(resolve => setTimeout(resolve, 200));
            } catch (error) {
                console.error(`下载图片失败 ${i + 1}:`, error);
            }
        }
    }

    // ==================== 批量下载功能 ====================
    
    // 注意：所有批量下载相关的变量已在上面声明，这里不再重复声明

    // 模式切换和批量下载相关
    const singleModeBtn = document.getElementById('singleModeBtn');
    const batchModeBtn = document.getElementById('batchModeBtn');
    const fetchArticlesBtn = document.getElementById('fetchArticlesBtn');
    const articleListInfo = document.getElementById('articleListInfo');
    const selectedCount = document.getElementById('selectedCount');

    function switchMode(mode) {
        currentMode = mode;
        if (mode === 'single') {
            singleDownloadSection.style.display = 'block';
            batchDownloadSection.style.display = 'none';
            singleModeBtn.style.background = '#667eea';
            batchModeBtn.style.background = '#6c757d';
        } else {
            singleDownloadSection.style.display = 'none';
            batchDownloadSection.style.display = 'block';
            singleModeBtn.style.background = '#6c757d';
            batchModeBtn.style.background = '#667eea';
        }
    }

    singleModeBtn.addEventListener('click', () => switchMode('single'));
    batchModeBtn.addEventListener('click', () => switchMode('batch'));

    /**
     * 从文章页面提取公众号信息
     */
    async function extractBizFromArticle(tabId) {
        try {
            // 方法1: 从 URL 参数中提取
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (tab.url && tab.url.includes('/s/')) {
                const urlParams = new URLSearchParams(tab.url.split('?')[1]);
                let biz = urlParams.get('__biz');
                
                if (biz) {
                    return biz;
                }
            }

            // 方法2: 从页面内容中提取
            const results = await chrome.scripting.executeScript({
                target: { tabId: tabId },
                func: () => {
                    // 从 URL 中提取
                    const urlParams = new URLSearchParams(window.location.search);
                    let biz = urlParams.get('__biz');
                    if (biz) return biz;

                    // 从页面源码中提取
                    const html = document.documentElement.innerHTML;
                    const bizMatch = html.match(/__biz=([A-Za-z0-9_]+)/);
                    if (bizMatch && bizMatch[1]) {
                        return bizMatch[1];
                    }

                    // 从 JavaScript 变量中提取
                    const varMatch = html.match(/var\s+__biz\s*=\s*"([^"]+)"/);
                    if (varMatch && varMatch[1]) {
                        return varMatch[1];
                    }

                    // 从链接中提取
                    const links = document.querySelectorAll('a[href*="__biz"]');
                    for (const link of links) {
                        const href = link.href || link.getAttribute('href');
                        if (href) {
                            const match = href.match(/__biz=([A-Za-z0-9_]+)/);
                            if (match && match[1]) {
                                return match[1];
                            }
                        }
                    }

                    return null;
                }
            });

            if (results && results[0] && results[0].result) {
                return results[0].result;
            }

            return null;
        } catch (error) {
            console.error('提取 biz 失败:', error);
            return null;
        }
    }

    /**
     * 获取公众号文章列表
     */
    async function fetchArticleList() {
        try {
            updateStatus('⏳ 正在获取文章列表，请稍候...', 'info');
            fetchArticlesBtn.disabled = true;
            fetchArticlesBtn.textContent = '⏳ 正在获取...';

            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            
            if (!tab.url || !tab.url.includes('mp.weixin.qq.com')) {
                updateStatus('❌ 请在微信公众号页面使用此功能', 'error');
                fetchArticlesBtn.disabled = false;
                fetchArticlesBtn.textContent = '📋 获取该作者的所有文章';
                return;
            }

            // 从当前页面提取公众号信息
            let biz = '';
            
            if (tab.url.includes('/s/')) {
                // 从文章页面提取
                updateStatus('⏳ 正在从文章页面提取公众号信息...', 'info');
                biz = await extractBizFromArticle(tab.id);
                
                if (!biz) {
                    updateStatus('⚠️ 无法从当前页面获取公众号信息\n请尝试：\n1. 刷新页面后重试\n2. 或访问公众号主页', 'error');
                    fetchArticlesBtn.disabled = false;
                    fetchArticlesBtn.textContent = '📋 获取该作者的所有文章';
                    return;
                }
            } else if (tab.url.includes('profile_ext') || tab.url.includes('profile')) {
                // 已经在公众号主页
                const urlParams = new URLSearchParams(tab.url.split('?')[1]);
                biz = urlParams.get('__biz');
            }

            if (!biz) {
                updateStatus('⚠️ 无法获取公众号信息，请确保在公众号文章页面或主页', 'error');
                fetchArticlesBtn.disabled = false;
                fetchArticlesBtn.textContent = '📋 获取该作者的所有文章';
                return;
            }

            updateStatus('⏳ 正在获取该作者的所有文章...', 'info');

            // 使用微信公众号的 API 获取文章列表
            updateStatus('⏳ 正在通过 API 获取文章列表...', 'info');

            // 方法1: 尝试使用微信公众号的 profile_ext API
            // 在当前标签页打开公众号主页（如果不在主页）
            if (!tab.url.includes('profile') && !tab.url.includes('homepage')) {
                updateStatus('⏳ 正在跳转到公众号主页...', 'info');
                try {
                    await chrome.tabs.update(tab.id, { url: `https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=${biz}` });
                    // 等待页面加载
                    await waitForTabLoad(tab.id, 10000);
                    await new Promise(resolve => setTimeout(resolve, 2000));
                } catch (e) {
                    console.error('跳转失败，尝试在当前页面提取:', e);
                }
            }

            const [currentTab] = await chrome.tabs.query({ active: true, currentWindow: true });

            updateStatus('⏳ 正在滚动页面加载更多内容...', 'info');
            
            // 先滚动页面以加载更多内容（仅在公众号主页时）
            if (currentTab.url.includes('profile') || currentTab.url.includes('homepage')) {
                for (let i = 0; i < 5; i++) {
                    try {
                        await chrome.scripting.executeScript({
                            target: { tabId: currentTab.id },
                            func: () => {
                                window.scrollTo(0, document.body.scrollHeight);
                            }
                        });
                        await new Promise(resolve => setTimeout(resolve, 1500));
                    } catch (e) {
                        console.error('滚动失败:', e);
                        break;
                    }
                }
            }

            updateStatus('⏳ 正在提取文章列表...', 'info');

            // 注入脚本获取文章列表（多种方法）
            const results = await chrome.scripting.executeScript({
                target: { tabId: currentTab.id },
                func: (bizParam) => {
                    console.log('开始提取文章列表，biz:', bizParam);
                    console.log('当前页面URL:', window.location.href);
                    console.log('页面标题:', document.title);
                    const articles = [];
                    const foundUrls = new Set();
                    
                    // 调试：检查页面结构
                    console.log('页面body内容长度:', document.body.innerHTML.length);
                    console.log('查找所有包含 /s/ 的链接...');

                    // 方法1: 从页面 DOM 中提取（扩展选择器）
                    // 先尝试查找所有包含 /s/ 的链接
                    const allLinks = document.querySelectorAll('a[href*="/s/"], a[href*="mp.weixin.qq.com/s/"]');
                    console.log(`找到 ${allLinks.length} 个包含 /s/ 的链接`);
                    
                    const linkSelectors = [
                        'a[href*="/s/"]',
                        'a[href*="mp.weixin.qq.com/s/"]',
                        '.weui_media_box a',
                        '.msg_item a',
                        '.msg_card a',
                        '.js_article_list a',
                        '.article-list a',
                        '.profile_article_item a',
                        '.article_item a',
                        '.msg_item',
                        '.weui_media_box',
                        '[class*="article"] a',
                        '[class*="msg"] a',
                        '[id*="article"] a',
                        '[id*="msg"] a'
                    ];

                    console.log('方法1: 从 DOM 中提取');
                    
                    // 如果直接找到了链接，先处理它们
                    if (allLinks.length > 0) {
                        console.log('直接处理找到的链接...');
                        allLinks.forEach((link, idx) => {
                            try {
                                let href = link.href || link.getAttribute('href');
                                if (!href) return;
                                
                                console.log(`链接 ${idx + 1}:`, href.substring(0, 100));
                                
                                // 处理相对路径和绝对路径
                                if (href.startsWith('/')) {
                                    href = 'https://mp.weixin.qq.com' + href;
                                } else if (!href.startsWith('http')) {
                                    return;
                                }
                                
                                if (href.includes('/s/')) {
                                    const baseUrl = href.split('?')[0];
                                    if (!foundUrls.has(baseUrl)) {
                                        foundUrls.add(baseUrl);
                                        
                                        // 确保包含 __biz 参数
                                        if (!href.includes('__biz=') && bizParam) {
                                            const separator = href.includes('?') ? '&' : '?';
                                            href = `${href}${separator}__biz=${bizParam}`;
                                        }
                                        
                                        // 获取标题
                                        let title = link.textContent.trim() || 
                                                   link.getAttribute('title') || 
                                                   link.closest('[class*="title"]')?.textContent.trim() ||
                                                   `文章 ${articles.length + 1}`;
                                        
                                        articles.push({
                                            url: href,
                                            title: title,
                                            time: '',
                                            index: articles.length
                                        });
                                    }
                                }
                            } catch (e) {
                                console.error('处理链接失败:', e);
                            }
                        });
                    }
                    
                    // 然后尝试使用选择器
                    for (const selector of linkSelectors) {
                        try {
                            const links = document.querySelectorAll(selector);
                            if (links.length > 0) {
                                console.log(`选择器 ${selector} 找到 ${links.length} 个元素`);
                            }
                            
                            links.forEach(link => {
                                let href = link.href || link.getAttribute('href');
                                if (!href) return;
                                
                                // 处理相对路径和绝对路径
                                if (href.startsWith('/')) {
                                    href = 'https://mp.weixin.qq.com' + href;
                                } else if (!href.startsWith('http')) {
                                    return; // 跳过无效链接
                                }
                                
                                if (href.includes('/s/')) {
                                    // 确保包含 __biz 参数
                                    if (!href.includes('__biz=') && bizParam) {
                                        const separator = href.includes('?') ? '&' : '?';
                                        href = `${href}${separator}__biz=${bizParam}`;
                                    }
                                    
                                    // 提取基础 URL（去除参数，只保留 /s/xxx 部分）
                                    const baseUrl = href.split('?')[0];
                                    if (!foundUrls.has(baseUrl)) {
                                        foundUrls.add(baseUrl);
                                        
                                        // 获取标题
                                        let title = '';
                                        const parent = link.closest('.weui_media_box, .msg_item, .msg_card, .js_article_item, .profile_article_item, .article_item, [class*="article"], [class*="msg"]');
                                        if (parent) {
                                            const titleSelectors = ['.weui_media_title', '.msg_title', '.article-title', 'h4', 'h3', 'h2', '.title', '[class*="title"]'];
                                            for (const ts of titleSelectors) {
                                                const titleEl = parent.querySelector(ts);
                                                if (titleEl) {
                                                    title = titleEl.textContent.trim();
                                                    break;
                                                }
                                            }
                                            if (!title) {
                                                title = link.textContent.trim();
                                            }
                                        } else {
                                            title = link.textContent.trim();
                                        }
                                        
                                        // 获取时间
                                        let time = '';
                                        if (parent) {
                                            const timeSelectors = ['.weui_media_extra_info', '.msg_date', '.date', '.time', '.publish-time', '[class*="date"]', '[class*="time"]'];
                                            for (const ts of timeSelectors) {
                                                const timeEl = parent.querySelector(ts);
                                                if (timeEl) {
                                                    time = timeEl.textContent.trim();
                                                    break;
                                                }
                                            }
                                        }
                                        
                                        articles.push({
                                            url: href,
                                            title: title || `文章 ${articles.length + 1}`,
                                            time: time,
                                            index: articles.length
                                        });
                                    }
                                }
                            });
                        } catch (e) {
                            console.error(`选择器 ${selector} 出错:`, e);
                        }
                    }

                    console.log(`方法1找到 ${articles.length} 篇文章`);

                    // 方法2: 从页面源码中提取所有文章 URL
                    console.log('方法2: 从页面源码中提取');
                    const html = document.documentElement.innerHTML;
                    const urlPatterns = [
                        /https?:\/\/mp\.weixin\.qq\.com\/s\/[a-zA-Z0-9_-]+/g,
                        /\/s\/[a-zA-Z0-9_-]+/g
                    ];
                    
                    for (const pattern of urlPatterns) {
                        const urlMatches = html.match(pattern);
                        if (urlMatches) {
                            const uniqueUrls = [...new Set(urlMatches)];
                            uniqueUrls.forEach((url) => {
                                // 处理相对路径
                                let fullUrl = url;
                                if (url.startsWith('/')) {
                                    fullUrl = 'https://mp.weixin.qq.com' + url;
                                }
                                
                                const baseUrl = fullUrl.split('?')[0];
                                if (!foundUrls.has(baseUrl) && fullUrl.includes('/s/')) {
                                    foundUrls.add(baseUrl);
                                    
                                    // 确保包含 __biz 参数
                                    if (!fullUrl.includes('__biz=') && bizParam) {
                                        const separator = fullUrl.includes('?') ? '&' : '?';
                                        fullUrl = `${fullUrl}${separator}__biz=${bizParam}`;
                                    }
                                    
                                    articles.push({
                                        url: fullUrl,
                                        title: `文章 ${articles.length + 1}`,
                                        time: '',
                                        index: articles.length
                                    });
                                }
                            });
                        }
                    }

                    console.log(`方法2后总共找到 ${articles.length} 篇文章`);

                    // 方法3: 尝试从 JavaScript 变量中提取
                    console.log('方法3: 从 JavaScript 变量中提取');
                    try {
                        // 查找各种可能的变量名
                        const varPatterns = [
                            /var\s+msgList\s*=\s*(\[.*?\])/,
                            /msgList\s*[:=]\s*(\[.*?\])/,
                            /articleList\s*[:=]\s*(\[.*?\])/,
                            /list\s*[:=]\s*(\[.*?\])/
                        ];
                        
                        for (const pattern of varPatterns) {
                            const match = html.match(pattern);
                            if (match) {
                                try {
                                    const listData = JSON.parse(match[1]);
                                    if (Array.isArray(listData)) {
                                        listData.forEach((item, index) => {
                                            if (item && item.link) {
                                                let url = item.link;
                                                if (url.includes('/s/')) {
                                                    const baseUrl = url.split('?')[0];
                                                    if (!foundUrls.has(baseUrl)) {
                                                        foundUrls.add(baseUrl);
                                                        if (!url.includes('__biz=') && bizParam) {
                                                            const separator = url.includes('?') ? '&' : '?';
                                                            url = `${url}${separator}__biz=${bizParam}`;
                                                        }
                                                        articles.push({
                                                            url: url,
                                                            title: item.title || `文章 ${articles.length + 1}`,
                                                            time: item.time || '',
                                                            index: articles.length
                                                        });
                                                    }
                                                }
                                            }
                                        });
                                    }
                                } catch (e) {
                                    // JSON 解析失败，继续
                                }
                            }
                        }
                    } catch (e) {
                        console.error('方法3出错:', e);
                    }

                    console.log(`最终找到 ${articles.length} 篇文章`);
                    return articles.slice(0, 100); // 最多100篇
                },
                args: [biz]
            });

            if (results && results[0] && results[0].result) {
                articleListData = results[0].result;
                console.log('提取到的文章列表:', articleListData);
                
                if (articleListData.length === 0) {
                    // 提供更详细的错误信息和解决建议
                    updateStatus('⚠️ 未找到文章列表\n\n可能原因：\n1. 公众号主页需要登录\n2. 页面结构发生变化\n3. 公众号没有公开文章\n4. 当前不在正确的页面\n\n建议：\n1. 确保已登录微信\n2. 访问公众号主页（profile_ext）\n3. 手动滚动页面加载更多\n4. 等待页面完全加载后重试\n5. 刷新页面后重试', 'error');
                    fetchArticlesBtn.disabled = false;
                    fetchArticlesBtn.textContent = '📋 获取该作者的所有文章';
                    return;
                }

                updateStatus(`✅ 成功找到 ${articleListData.length} 篇文章！`, 'success');
                displayArticleList(articleListData);
                articleListInfo.style.display = 'block';
                articleList.style.display = 'block';
                articleCount.textContent = articleListData.length;
                fetchArticlesBtn.disabled = false;
                fetchArticlesBtn.textContent = '🔄 重新获取文章列表';
            } else {
                console.error('提取结果为空或格式错误:', results);
                updateStatus('⚠️ 无法获取文章列表\n\n请尝试：\n1. 刷新公众号主页\n2. 手动滚动页面加载更多\n3. 确保页面完全加载\n4. 检查浏览器控制台查看详细错误', 'error');
                fetchArticlesBtn.disabled = false;
                fetchArticlesBtn.textContent = '📋 获取该作者的所有文章';
            }

        } catch (error) {
            console.error('获取文章列表失败:', error);
            updateStatus('❌ 获取文章列表失败: ' + (error.message || '未知错误'), 'error');
            fetchArticlesBtn.disabled = false;
            fetchArticlesBtn.textContent = '📋 获取当前公众号文章列表';
        }
    }

    /**
     * 显示文章列表
     */
    function displayArticleList(articles) {
        articleList.innerHTML = '';
        selectedArticles.clear();

        articles.forEach((article, index) => {
            const item = document.createElement('div');
            item.style.cssText = 'padding: 8px; margin-bottom: 5px; border: 1px solid #e0e0e0; border-radius: 4px; display: flex; align-items: center; gap: 8px;';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = true;
            checkbox.style.cssText = 'cursor: pointer;';
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    selectedArticles.add(index);
                } else {
                    selectedArticles.delete(index);
                }
                updateSelectedCount();
            });
            selectedArticles.add(index);

            const label = document.createElement('label');
            label.style.cssText = 'flex: 1; cursor: pointer; font-size: 12px;';
            label.textContent = `${index + 1}. ${article.title} ${article.time ? '(' + article.time + ')' : ''}`;
            label.addEventListener('click', () => checkbox.click());

            item.appendChild(checkbox);
            item.appendChild(label);
            articleList.appendChild(item);
        });

        updateSelectedCount();
    }

    /**
     * 更新选中数量
     */
    function updateSelectedCount() {
        const count = selectedArticles.size;
        selectedCount.textContent = count;
        batchDownloadBtn.disabled = count === 0 || isBatchDownloading;
        batchDownloadBtn.style.display = count > 0 ? 'block' : 'none';
    }

    /**
     * 全选/取消全选
     */
    selectAllBtn.addEventListener('click', () => {
        const checkboxes = articleList.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach((cb, index) => {
            cb.checked = true;
            selectedArticles.add(index);
        });
        updateSelectedCount();
    });

    selectNoneBtn.addEventListener('click', () => {
        const checkboxes = articleList.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach((cb, index) => {
            cb.checked = false;
            selectedArticles.delete(index);
        });
        updateSelectedCount();
    });

    /**
     * 等待标签页加载完成
     */
    async function waitForTabLoad(tabId, maxWait = 10000) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            
            const checkTab = async () => {
                try {
                    const tab = await chrome.tabs.get(tabId);
                    
                    if (tab.status === 'complete') {
                        // 额外等待一下确保内容加载
                        await new Promise(r => setTimeout(r, 1500));
                        resolve();
                    } else if (Date.now() - startTime > maxWait) {
                        reject(new Error('页面加载超时'));
                    } else {
                        setTimeout(checkTab, 500);
                    }
                } catch (error) {
                    reject(error);
                }
            };
            
            checkTab();
        });
    }

    /**
     * 批量下载文章（改进版）
     */
    async function batchDownloadArticles() {
        if (selectedArticles.size === 0 || isBatchDownloading) {
            return;
        }

        isBatchDownloading = true;
        batchDownloadPaused = false;
        batchDownloadCancelled = false;
        batchProgress.style.display = 'block';
        batchDownloadBtn.disabled = true;
        fetchArticlesBtn.disabled = true;
        pauseBatchBtn.disabled = false;
        cancelBatchBtn.disabled = false;

        const selectedIndices = Array.from(selectedArticles).sort((a, b) => a - b);
        const total = selectedIndices.length;
        let completed = 0;
        let failed = 0;
        const failedArticles = [];

        const format = formatSelect.value;

        console.log(`开始批量下载 ${total} 篇文章`);

        for (let i = 0; i < selectedIndices.length; i++) {
            if (batchDownloadCancelled) {
                updateStatus('❌ 批量下载已取消', 'error');
                break;
            }

            // 等待暂停状态解除
            while (batchDownloadPaused && !batchDownloadCancelled) {
                await new Promise(resolve => setTimeout(resolve, 500));
            }

            if (batchDownloadCancelled) break;

            const articleIndex = selectedIndices[i];
            const article = articleListData[articleIndex];
            let tab = null;

            try {
                const current = i + 1;
                progressText.textContent = `${current}/${total}`;
                progressBar.style.width = `${(current / total) * 100}%`;
                updateStatus(`📥 [${current}/${total}] 正在下载: ${article.title}`, 'info');

                console.log(`处理文章 ${current}/${total}: ${article.title}`);

                // 打开文章页面
                try {
                    tab = await chrome.tabs.create({ 
                        url: article.url, 
                        active: false 
                    });
                    console.log(`已创建标签页: ${tab.id}`);
                } catch (tabError) {
                    console.error('创建标签页失败:', tabError);
                    throw new Error('无法打开文章页面');
                }

                // 等待页面加载完成
                try {
                    await waitForTabLoad(tab.id, 15000);
                    console.log(`标签页 ${tab.id} 加载完成`);
                } catch (loadError) {
                    console.error('页面加载超时:', loadError);
                    if (tab) chrome.tabs.remove(tab.id);
                    throw new Error('页面加载超时，请检查网络连接');
                }

                // 注入 content script
                let extractSuccess = false;
                let retryCount = 0;
                const maxRetries = 3;

                while (!extractSuccess && retryCount < maxRetries && !batchDownloadCancelled) {
                    try {
                        // 确保 content script 已注入
                        await chrome.scripting.executeScript({
                            target: { tabId: tab.id },
                            files: ['content.js']
                        });
                        
                        // 等待脚本初始化
                        await new Promise(resolve => setTimeout(resolve, 1500));

                        // 发送提取消息
                        const response = await chrome.tabs.sendMessage(tab.id, { action: 'extract' });
                        
                        if (response && response.success && response.data) {
                            const data = response.data;
                            
                            // 验证数据有效性
                            if (!data.content && !data.title) {
                                throw new Error('文章内容为空');
                            }

                            const content = generateFileContent(data, format, false);
                            const title = (data.title || article.title || '未命名文章')
                                .replace(/[<>:"/\\|?*]/g, '_')
                                .substring(0, 50);
                            const extension = format === 'html' ? 'html' : 
                                           format === 'markdown' ? 'md' : 
                                           format === 'pdf' ? 'pdf' : 'txt';
                            const filename = `${title}.${extension}`;

                            if (format === 'pdf') {
                                updateStatus(`⚠️ PDF 格式暂不支持批量下载，跳过: ${title}`, 'info');
                                completed++;
                                extractSuccess = true;
                            } else {
                                const mimeType = format === 'html' ? 'text/html' : 
                                              format === 'markdown' ? 'text/markdown' : 'text/plain';
                                
                                // 使用 data URL 下载
                                const dataUrl = `data:${mimeType};charset=utf-8,${encodeURIComponent(content)}`;

                                try {
                                    await chrome.downloads.download({
                                        url: dataUrl,
                                        filename: filename,
                                        saveAs: false
                                    });
                                    console.log(`成功下载: ${filename}`);
                                    completed++;
                                    extractSuccess = true;
                                } catch (downloadError) {
                                    console.error('下载文件失败:', downloadError);
                                    throw new Error('文件下载失败');
                                }
                            }
                        } else {
                            throw new Error('无法提取文章内容');
                        }
                    } catch (extractError) {
                        retryCount++;
                        console.error(`提取失败 (尝试 ${retryCount}/${maxRetries}):`, extractError);
                        
                        if (retryCount < maxRetries) {
                            updateStatus(`⚠️ 提取失败，重试中 (${retryCount}/${maxRetries})...`, 'info');
                            await new Promise(resolve => setTimeout(resolve, 2000));
                        } else {
                            throw extractError;
                        }
                    }
                }

                if (!extractSuccess) {
                    failed++;
                    failedArticles.push(article.title);
                    console.error(`文章下载失败: ${article.title}`);
                }

            } catch (error) {
                console.error(`下载文章失败 ${article.title}:`, error);
                failed++;
                failedArticles.push(article.title);
            } finally {
                // 确保关闭标签页
                if (tab && tab.id) {
                    try {
                        await chrome.tabs.remove(tab.id);
                    } catch (e) {
                        console.error('关闭标签页失败:', e);
                    }
                }

                // 添加延迟避免请求过快（根据进度调整延迟）
                const delay = i < 5 ? 2000 : 1500; // 前5篇延迟更长
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }

        // 恢复状态
        isBatchDownloading = false;
        batchDownloadPaused = false;
        batchProgress.style.display = 'none';
        batchDownloadBtn.disabled = false;
        fetchArticlesBtn.disabled = false;
        pauseBatchBtn.disabled = true;
        cancelBatchBtn.disabled = true;

        // 显示结果
        let resultMessage = `✅ 批量下载完成！\n成功: ${completed}/${total}`;
        if (failed > 0) {
            resultMessage += `\n失败: ${failed}/${total}`;
            if (failedArticles.length > 0 && failedArticles.length <= 5) {
                resultMessage += `\n失败的文章: ${failedArticles.join(', ')}`;
            }
        }
        updateStatus(resultMessage, failed === 0 ? 'success' : 'error');
        progressBar.style.width = '100%';

        console.log(`批量下载完成: 成功 ${completed}, 失败 ${failed}`);
    }

    pauseBatchBtn.addEventListener('click', () => {
        batchDownloadPaused = !batchDownloadPaused;
        pauseBatchBtn.textContent = batchDownloadPaused ? '继续' : '暂停';
    });

    cancelBatchBtn.addEventListener('click', () => {
        if (confirm('确定要取消批量下载吗？')) {
            batchDownloadCancelled = true;
            batchDownloadPaused = false;
        }
    });

    fetchArticlesBtn.addEventListener('click', fetchArticleList);
    batchDownloadBtn.addEventListener('click', batchDownloadArticles);

    // ==================== 事件监听 ====================
    downloadBtn.addEventListener('click', () => downloadArticle(false));
    downloadWithImagesBtn.addEventListener('click', () => downloadArticle(true));

    // 初始化
    checkCurrentTab();
});
