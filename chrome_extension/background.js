/**
 * Background Service Worker
 * 处理后台任务和消息传递
 */

// 扩展安装时的处理
chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') {
        console.log('微信公众号文章下载器已安装');
        // 可以在这里打开欢迎页面
        chrome.tabs.create({
            url: chrome.runtime.getURL('welcome.html')
        });
    }
});

// 监听来自 content script 或 popup 的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'download') {
        // 处理下载请求
        handleDownload(request.data)
            .then(() => sendResponse({ success: true }))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true; // 保持消息通道开放
    }
});

/**
 * 处理下载
 */
async function handleDownload(data) {
    // 这里可以添加额外的下载逻辑
    console.log('处理下载请求:', data);
}
