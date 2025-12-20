/**
 * Background Service Worker
 * 处理后台任务和消息传递
 */

// 监听扩展安装
chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') {
        console.log('微信公众号文章下载器已安装');
        // 可以在这里打开欢迎页面
        chrome.tabs.create({
            url: 'welcome.html'
        });
    }
});

// 监听下载事件
chrome.downloads.onDeterminingFilename.addListener((downloadItem, suggest) => {
    // 可以在这里自定义下载文件名
    console.log('下载文件:', downloadItem);
});

// 处理来自 content script 的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'downloadArticle') {
        // 处理文章下载请求
        handleArticleDownload(request.data)
            .then(result => sendResponse({ success: true, result }))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true; // 保持消息通道开放
    }
});

// 处理文章下载
async function handleArticleDownload(articleData) {
    // 这里可以添加额外的处理逻辑
    // 比如保存到云存储、同步等
    return { message: '下载处理完成' };
}

