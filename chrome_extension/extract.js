/**
 * 注入到文章页面执行，返回元数据和清洗后的正文 HTML。
 * 通过 chrome.scripting.executeScript({ func }) 传入，函数体必须自包含。
 */
function extractWeChatArticle() {
    const html = document.documentElement.innerHTML;

    function decode(raw) {
        const simple = { n: '\n', r: '\r', t: '\t', b: '\b', f: '\f', v: '\v', 0: '\0' };
        const box = document.createElement('textarea');
        box.innerHTML = raw.replace(/\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|[\s\S])/g, (all, esc) =>
            esc.length > 1 ? String.fromCharCode(parseInt(esc.slice(1), 16)) : (simple[esc] ?? esc));
        return box.value.trim();
    }

    // 与 parse.py 的 extract_js_var 相同：兼容 htmlDecode("…")、'…'.html(false)、"" || "…"
    function jsVar(name) {
        const decl = new RegExp('\\bvar\\s+' + name + '\\s*=\\s*', 'g');
        const literal = /(["'])((?:\\.|(?!\1)[\s\S])*)\1/y;
        const skip = (pos, token) => {
            while (html[pos] === ' ' || html[pos] === '\t') pos += 1;
            return html.startsWith(token, pos) ? skip(pos + token.length, token) : pos;
        };
        let m;
        while ((m = decl.exec(html)) !== null) {
            let pos = m.index + m[0].length;
            for (;;) {
                literal.lastIndex = skip(pos, 'htmlDecode(');
                const lit = literal.exec(html);
                if (!lit) break;
                const value = decode(lit[2]);
                if (value) return value;
                pos = skip(literal.lastIndex, ')');
                if (!html.startsWith('||', pos)) break;
                pos += 2;
            }
        }
        return '';
    }

    function text(selector) {
        const node = document.querySelector(selector);
        return node ? node.textContent.replace(/\s+/g, ' ').trim() : '';
    }

    function meta(prop) {
        const node = document.querySelector(`meta[property="${prop}"], meta[name="${prop}"]`);
        return node ? (node.getAttribute('content') || '').trim() : '';
    }

    const content = document.querySelector('#js_content');
    if (!content) {
        const verify = /环境异常|完成验证/.test(document.body ? document.body.textContent : '');
        return { error: verify ? '页面要求验证，请先在页面上完成验证再保存' : '没有找到文章正文（图片/视频分享类消息暂不支持）' };
    }

    function normalizeSrc(src) {
        src = (src || '').trim();
        if (src.startsWith('//')) src = 'https:' + src;
        if (src.startsWith('http://mmbiz.qpic.cn')) src = 'https://' + src.slice('http://'.length);
        return src.startsWith('data:') ? '' : src;
    }

    function normalizeUrl(url) {
        try {
            const u = new URL(url);
            if (u.protocol === 'http:') u.protocol = 'https:';
            u.hash = '';
            return u.toString();
        } catch (e) {
            return url;
        }
    }

    const body = content.cloneNode(true);
    body.querySelectorAll([
        'script', 'style', 'noscript', 'iframe',
        'mp-common-profile', 'mp-common-mpaudio', 'mp-common-videosnap',
        'mp-miniprogram', 'mpvoice', 'qqmusic', 'mpvote',
        'ul.code-snippet__line-index'
    ].join(',')).forEach(node => node.remove());
    body.querySelectorAll('img').forEach(img => {
        img.setAttribute('src', normalizeSrc(img.getAttribute('data-src') || img.getAttribute('src')));
        if (img.getAttribute('alt') === 'null') img.removeAttribute('alt');
    });

    const ts = parseInt(jsVar('create_time') || jsVar('ct'), 10);
    const digits = (...names) => names.map(jsVar).find(v => /^\d+$/.test(v)) || '';

    // 字段优先级与命令行版 wechat_downloader/parse.py 一致：页面变量优先，DOM 兜底
    return {
        title: jsVar('msg_title') || text('#activity-name') || meta('og:title') || '未命名文章',
        author: jsVar('author') || text('#js_author_name'),
        account: jsVar('nickname') || text('#js_name'),
        biz: jsVar('biz'),
        mid: digits('mid', 'appmsgid'),
        idx: digits('idx', 'itemidx'),
        userName: jsVar('user_name'),
        url: normalizeUrl(jsVar('msg_link') || location.href),
        requestUrl: location.href,
        sourceUrl: jsVar('msg_source_url'),
        publishTime: Number.isFinite(ts) && ts > 0 ? ts : 0,
        description: jsVar('msg_desc'),
        cover: normalizeSrc(jsVar('msg_cdn_url')),
        contentHtml: body.innerHTML
    };
}
