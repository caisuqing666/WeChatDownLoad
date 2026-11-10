const RECEIVER = 'http://127.0.0.1:4546';

const statusEl = document.getElementById('status');
const saveBtn = document.getElementById('saveBtn');
const sendBtn = document.getElementById('sendBtn');

let tab = null;
let article = null;

function setStatus(message, type = 'info') {
    statusEl.textContent = message;
    statusEl.className = `status ${type}`;
}

function isArticleUrl(url) {
    try {
        const u = new URL(url);
        return u.protocol === 'https:' && u.hostname === 'mp.weixin.qq.com' && u.pathname.startsWith('/s');
    } catch (e) {
        return false;
    }
}

function showArticle(a) {
    document.getElementById('articleTitle').textContent = a.title || '（无标题）';
    document.getElementById('articleAccount').textContent = a.account || '';
    document.getElementById('articleTime').textContent =
        a.publishTime ? new Date(a.publishTime * 1000).toLocaleDateString('zh-CN') : '';
    document.getElementById('articleInfo').hidden = false;
}

async function init() {
    [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !isArticleUrl(tab.url || '')) {
        setStatus('请先打开一篇公众号文章（mp.weixin.qq.com/s/…）', 'error');
        return;
    }
    sendBtn.disabled = false;

    try {
        const [{ result }] = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: extractWeChatArticle
        });
        if (!result || result.error) {
            setStatus(result ? result.error : '读取页面失败，请刷新后重试', 'error');
            return;
        }
        article = result;
        showArticle(article);
        setStatus('已读取文章', 'success');
        saveBtn.disabled = false;
    } catch (e) {
        setStatus('读取页面失败：' + (e.message || e), 'error');
    }
}

async function save() {
    saveBtn.disabled = true;
    try {
        const markdown = WeChatMarkdown.render(article);
        const folder = WeChatMarkdown.safeFilename(article.account || '未知公众号');
        const filename = `公众号/${folder}/${WeChatMarkdown.filename(article)}`;
        await chrome.downloads.download({
            url: 'data:text/markdown;charset=utf-8,' + encodeURIComponent(markdown),
            filename,
            conflictAction: 'uniquify',
            saveAs: false
        });
        setStatus(`已保存到 下载/${filename}`, 'success');
    } catch (e) {
        setStatus('保存失败：' + (e.message || e), 'error');
    } finally {
        saveBtn.disabled = false;
    }
}

async function send() {
    sendBtn.disabled = true;
    const url = (article && article.url && isArticleUrl(article.url)) ? article.url : tab.url;
    try {
        const resp = await fetch(`${RECEIVER}/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP ${resp.status}`);
        setStatus(`已发送给本地命令行（排队 ${data.queued} 篇），进度看终端输出`, 'success');
    } catch (e) {
        const offline = e instanceof TypeError;
        setStatus(offline
            ? '连不上本地命令行，请先运行 python -m wechat_downloader.receiver'
            : '发送失败：' + e.message, 'error');
    } finally {
        sendBtn.disabled = false;
    }
}

saveBtn.addEventListener('click', save);
sendBtn.addEventListener('click', send);
init();
