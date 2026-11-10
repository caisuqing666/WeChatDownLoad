/**
 * 正文 HTML -> Markdown，输出格式与命令行版（wechat_downloader/render.py）保持一致
 */
const WeChatMarkdown = (() => {
    const BLOCK = new Set(['P', 'DIV', 'SECTION', 'ARTICLE', 'HEADER', 'FOOTER', 'FIGURE', 'FIGCAPTION', 'TABLE']);

    function inline(text) {
        return text.replace(/[\s\u00a0]+/g, ' ');
    }

    function wrap(marker, inner) {
        const trimmed = inner.trim();
        return trimmed ? `${marker}${trimmed}${marker}` : inner;
    }

    function children(node, ctx) {
        return Array.from(node.childNodes).map(child => convert(child, ctx)).join('');
    }

    function list(node, ctx, ordered) {
        const depth = ctx.depth || 0;
        let index = 0;
        const items = Array.from(node.children).filter(li => li.tagName === 'LI').map(li => {
            index += 1;
            const marker = ordered ? `${index}. ` : '- ';
            const body = children(li, { ...ctx, depth: depth + 1 }).trim()
                .replace(/\n{2,}/g, '\n')
                .replace(/\n/g, '\n' + ' '.repeat(marker.length));
            return '  '.repeat(depth) + marker + body;
        });
        return `\n\n${items.join('\n')}\n\n`;
    }

    function table(node, ctx) {
        const rows = Array.from(node.querySelectorAll('tr')).map(tr =>
            Array.from(tr.children).map(cell => children(cell, ctx).replace(/\s+/g, ' ').replace(/\|/g, '\\|').trim()));
        if (!rows.length) return '';
        const width = Math.max(...rows.map(r => r.length));
        const line = r => '| ' + Array.from({ length: width }, (_, i) => r[i] || '').join(' | ') + ' |';
        const out = [line(rows[0]), line(Array(width).fill('---')), ...rows.slice(1).map(line)];
        return `\n\n${out.join('\n')}\n\n`;
    }

    function convert(node, ctx = {}) {
        if (node.nodeType === Node.TEXT_NODE) {
            return ctx.pre ? node.nodeValue : inline(node.nodeValue);
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return '';

        const tag = node.tagName;
        switch (tag) {
            case 'H1': case 'H2': case 'H3': case 'H4': case 'H5': case 'H6': {
                const text = children(node, ctx).replace(/\s+/g, ' ').trim();
                return text ? `\n\n${'#'.repeat(Number(tag[1]))} ${text}\n\n` : '';
            }
            case 'BR':
                return '  \n';
            case 'HR':
                return '\n\n---\n\n';
            case 'STRONG': case 'B':
                return wrap('**', children(node, ctx));
            case 'EM': case 'I':
                return wrap('*', children(node, ctx));
            case 'DEL': case 'S':
                return wrap('~~', children(node, ctx));
            case 'CODE':
                return ctx.pre ? node.textContent : wrap('`', node.textContent);
            case 'PRE': {
                // 微信代码块每行是一个 <code>：<pre><code>第1行</code><code>第2行</code></pre>
                const codes = Array.from(node.querySelectorAll('code'));
                const lang = (node.getAttribute('data-lang') || '').trim();
                // 换行规则与 parse.py 的 _flatten_code_blocks 一致：<br> 一律视为换行；
                // 逐行格式里空行写成 <code><br></code>，行尾的 <br> 只是占位，去掉一个
                const blocks = codes.length ? codes : [node];
                const lineText = el => {
                    const copy = el.cloneNode(true);
                    copy.querySelectorAll('br').forEach(br => br.replaceWith('\n'));
                    const line = copy.textContent;
                    return blocks.length > 1 && line.endsWith('\n') ? line.slice(0, -1) : line;
                };
                const body = blocks.map(lineText).join('\n');
                return `\n\n\`\`\`${lang}\n${body.replace(/\n+$/, '')}\n\`\`\`\n\n`;
            }
            case 'A': {
                const text = children(node, ctx).trim();
                const href = node.getAttribute('href') || '';
                if (!href || href.startsWith('javascript:')) return text;
                return text ? `[${text}](${href})` : '';
            }
            case 'IMG': {
                const src = node.getAttribute('src');
                return src ? `![${node.getAttribute('alt') || ''}](${src})` : '';
            }
            case 'UL':
                return list(node, ctx, false);
            case 'OL':
                return list(node, ctx, true);
            case 'BLOCKQUOTE': {
                const text = children(node, ctx).trim().replace(/\n{3,}/g, '\n\n');
                return text ? `\n\n${text.split('\n').map(l => l ? `> ${l}` : '>').join('\n')}\n\n` : '';
            }
            case 'TABLE':
                return table(node, ctx);
            default: {
                const text = children(node, ctx);
                return BLOCK.has(tag) ? `\n\n${text.trim()}\n\n` : text;
            }
        }
    }

    function htmlToMarkdown(html) {
        const doc = new DOMParser().parseFromString(`<body>${html}</body>`, 'text/html');
        return convert(doc.body)
            .replace(/(\S)[ \t]+\n/g, (m, c) => (m.endsWith('  \n') ? m : c + '\n'))
            .replace(/^[ \t]+$/gm, '')
            .replace(/\n{3,}/g, '\n\n')
            .trim() + '\n';
    }

    function isoChina(ts) {
        const d = new Date((ts + 8 * 3600) * 1000);
        return d.toISOString().replace(/\.\d{3}Z$/, '+08:00');
    }

    // 字段与顺序同 render.py：title/author/url/date 必有（可为空），其余有值才写
    function frontMatter(a) {
        const required = {
            title: a.title || '',
            author: a.author || '',
            url: a.url || '',
            date: a.publishTime ? isoChina(a.publishTime) : ''
        };
        const optional = {
            account: a.account,
            biz: a.biz,
            user_name: a.userName,
            source_url: a.sourceUrl,
            description: a.description,
            cover: a.cover,
            downloaded_at: isoChina(Math.floor(Date.now() / 1000))
        };
        const lines = [
            ...Object.entries(required),
            ...Object.entries(optional).filter(([, v]) => v)
        ].map(([k, v]) => `${k}: ${JSON.stringify(v)}`);
        return `---\n${lines.join('\n')}\n---\n`;
    }

    async function sha1Prefix(key) {
        const digest = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(key));
        return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('').slice(0, 8);
    }

    // 同 downloader.py 的 article_id：biz:mid:idx 的 SHA-1 前 8 位，取不到 biz/mid 时退回短链接短码
    function articleIdKey(a) {
        const urls = [a.url, a.requestUrl].filter(Boolean);
        const fromLinks = name => {
            for (const url of urls) {
                try {
                    const value = new URL(url).searchParams.get(name);
                    if (value) return value;
                } catch (e) {
                    // 忽略无法解析的链接
                }
            }
            return '';
        };
        const shortCode = url => {
            try {
                const path = new URL(url).pathname;
                return path.startsWith('/s/') ? path.slice(3).replace(/^\/+|\/+$/g, '') : '';
            } catch (e) {
                return '';
            }
        };
        const biz = a.biz || fromLinks('__biz');
        const mid = a.mid || fromLinks('mid');
        const idx = a.idx || fromLinks('idx') || '1';
        if (biz && mid) return `${biz}:${mid}:${idx}`;
        return urls.map(shortCode).find(Boolean) || a.url || '';
    }

    function articleId(a) {
        return sha1Prefix(articleIdKey(a));
    }

    function render(article) {
        return `${frontMatter(article)}\n# ${article.title}\n\n${htmlToMarkdown(article.contentHtml)}`;
    }

    // 同 downloader.py 的 safe_filename；maxBytes 按 UTF-8 计，给日期、ID 后缀留余量
    function safeFilename(name, maxLength = 80, maxBytes = 150) {
        const reserved = /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i;
        const encoder = new TextEncoder();
        let out = (name || '').normalize('NFC')
            .replace(/[<>:"/\\|?*\x00-\x1f]/g, '_')
            .replace(/\s+/g, ' ').trim().replace(/^\.+|\.+$/g, '');
        let chars = Array.from(out).slice(0, maxLength);
        while (encoder.encode(chars.join('')).length > maxBytes) chars.pop();
        out = chars.join('').replace(/[ .]+$/, '');
        if (!out) return '未命名';
        return reserved.test(out) ? `_${out}` : out;
    }

    async function filename(article) {
        const date = isoChina(article.publishTime || Math.floor(Date.now() / 1000)).slice(0, 10);
        return `${date}_${safeFilename(article.title)}_${await articleId(article)}.md`;
    }

    return { htmlToMarkdown, render, filename, safeFilename, articleId, frontMatter };
})();

if (typeof module !== 'undefined') {
    module.exports = WeChatMarkdown;
}
