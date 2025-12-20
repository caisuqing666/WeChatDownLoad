/**
 * Popup Script - 处理用户界面交互
 */

// DOM 元素
const downloadCurrentBtn = document.getElementById('downloadCurrent');
const downloadBatchBtn = document.getElementById('downloadBatch');
const downloadImagesCheckbox = document.getElementById('downloadImages');
const includeMetadataCheckbox = document.getElementById('includeMetadata');
const batchCountInput = document.getElementById('batchCount');
const statusDiv = document.getElementById('status');
const downloadHistoryDiv = document.getElementById('downloadHistory');
const clearHistoryBtn = document.getElementById('clearHistory');

// 显示状态消息
function showStatus(message, type = 'info') {
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;
    statusDiv.style.display = 'block';
    
    if (type === 'success') {
        setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 3000);
    }
}

// 获取当前活动标签页
async function getCurrentTab() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    return tab;
}

// 检查是否是微信公众号文章页面
async function checkArticlePage() {
    try {
        const tab = await getCurrentTab();
        if (!tab.url || !tab.url.includes('mp.weixin.qq.com/s/')) {
            showStatus('请在微信公众号文章页面使用此工具', 'error');
            downloadCurrentBtn.disabled = true;
            downloadBatchBtn.disabled = true;
            return false;
        }
        return true;
    } catch (error) {
        showStatus('无法获取当前页面信息', 'error');
        return false;
    }
}

// 下载单篇文章
async function downloadCurrentArticle() {
    try {
        const tab = await getCurrentTab();
        
        if (!tab.url || !tab.url.includes('mp.weixin.qq.com/s/')) {
            showStatus('请在微信公众号文章页面使用此工具', 'error');
            return;
        }

        showStatus('正在提取文章内容...', 'info');
        downloadCurrentBtn.disabled = true;

        // 向 content script 发送消息
        const response = await chrome.tabs.sendMessage(tab.id, { action: 'extractArticle' });

        if (!response || !response.success) {
            showStatus(response?.error || '提取文章内容失败', 'error');
            downloadCurrentBtn.disabled = false;
            return;
        }

        const articleData = response.data;
        showStatus('正在生成文件...', 'info');

        // 生成 Markdown 内容
        const markdown = generateMarkdown(articleData);

        // 下载文件
        const filename = sanitizeFilename(articleData.title) + '.md';
        await downloadFile(markdown, filename, 'text/markdown');

        // 保存到历史记录
        saveToHistory(articleData.title, articleData.url);

        showStatus('下载成功！', 'success');
        downloadCurrentBtn.disabled = false;

        // 如果启用图片下载
        if (downloadImagesCheckbox.checked && articleData.images.length > 0) {
            showStatus('开始下载图片...', 'info');
            await downloadImages(articleData.images, articleData.title);
        }

    } catch (error) {
        console.error('下载失败:', error);
        showStatus('下载失败: ' + error.message, 'error');
        downloadCurrentBtn.disabled = false;
    }
}

// 生成 Markdown 内容
function generateMarkdown(articleData) {
    let markdown = '';

    // 元数据
    if (includeMetadataCheckbox.checked) {
        markdown += '---\n';
        markdown += `title: ${articleData.title}\n`;
        if (articleData.author) {
            markdown += `author: ${articleData.author}\n`;
        }
        if (articleData.publishTime) {
            markdown += `publishTime: ${articleData.publishTime}\n`;
        }
        if (articleData.accountName) {
            markdown += `accountName: ${articleData.accountName}\n`;
        }
        markdown += `url: ${articleData.url}\n`;
        markdown += '---\n\n';
    }

    // 标题
    markdown += `# ${articleData.title}\n\n`;

    // 作者和时间
    if (includeMetadataCheckbox.checked) {
        if (articleData.author) {
            markdown += `**作者**: ${articleData.author}\n\n`;
        }
        if (articleData.publishTime) {
            markdown += `**发布时间**: ${articleData.publishTime}\n\n`;
        }
        markdown += '---\n\n';
    }

    // 封面图
    if (articleData.coverUrl) {
        markdown += `![封面](${articleData.coverUrl})\n\n`;
    }

    // 正文
    markdown += articleData.markdown;

    return markdown;
}

// 清理文件名
function sanitizeFilename(filename) {
    return filename
        .replace(/[<>:"/\\|?*]/g, '_')
        .replace(/\s+/g, '_')
        .substring(0, 100);
}

// 下载文件
function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    
    return chrome.downloads.download({
        url: url,
        filename: filename,
        saveAs: false
    });
}

// 下载图片
async function downloadImages(images, articleTitle) {
    const sanitizedTitle = sanitizeFilename(articleTitle);
    
    for (let i = 0; i < Math.min(images.length, 20); i++) {
        const image = images[i];
        const extension = getImageExtension(image.url);
        const filename = `${sanitizedTitle}_images/image_${i + 1}${extension}`;
        
        try {
            await chrome.downloads.download({
                url: image.url,
                filename: filename,
                saveAs: false
            });
        } catch (error) {
            console.error(`下载图片失败 ${image.url}:`, error);
        }
    }
}

// 获取图片扩展名
function getImageExtension(url) {
    const match = url.match(/\.(jpg|jpeg|png|gif|webp)(\?|$)/i);
    return match ? '.' + match[1].toLowerCase() : '.jpg';
}

// 保存到历史记录
function saveToHistory(title, url) {
    chrome.storage.local.get(['downloadHistory'], (result) => {
        const history = result.downloadHistory || [];
        history.unshift({
            title,
            url,
            time: new Date().toLocaleString('zh-CN')
        });
        
        // 只保留最近50条
        if (history.length > 50) {
            history.pop();
        }
        
        chrome.storage.local.set({ downloadHistory: history }, () => {
            loadHistory();
        });
    });
}

// 加载历史记录
function loadHistory() {
    chrome.storage.local.get(['downloadHistory'], (result) => {
        const history = result.downloadHistory || [];
        
        if (history.length === 0) {
            downloadHistoryDiv.innerHTML = '<p class="empty">暂无下载记录</p>';
            return;
        }
        
        downloadHistoryDiv.innerHTML = history.map(item => `
            <div class="history-item">
                <div class="title">${item.title}</div>
                <div class="time">${item.time}</div>
            </div>
        `).join('');
    });
}

// 批量下载（需要用户手动操作）
async function startBatchDownload() {
    const count = parseInt(batchCountInput.value) || 10;
    
    if (count < 1 || count > 100) {
        showStatus('下载数量应在1-100之间', 'error');
        return;
    }

    showStatus('批量下载功能需要手动操作，请按照提示进行', 'info');
    
    // 这里可以实现自动批量下载逻辑
    // 但由于微信公众号的限制，建议用户手动操作
    // 可以打开一个新标签页显示操作指南
    chrome.tabs.create({
        url: chrome.runtime.getURL('batch-guide.html')
    });
}

// 清空历史记录
function clearHistory() {
    if (confirm('确定要清空下载历史吗？')) {
        chrome.storage.local.set({ downloadHistory: [] }, () => {
            loadHistory();
            showStatus('历史记录已清空', 'success');
        });
    }
}

// 事件监听
downloadCurrentBtn.addEventListener('click', downloadCurrentArticle);
downloadBatchBtn.addEventListener('click', startBatchDownload);
clearHistoryBtn.addEventListener('click', clearHistory);

// 初始化
(async () => {
    await checkArticlePage();
    loadHistory();
})();

