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
                const first = codes[0];
                const lang = (node.getAttribute('data-lang') || '').trim()
                    || (first ? ((first.className.match(/language-(\S+)/) || [])[1] || '') : '');
                const lineText = el => {
                    const copy = el.cloneNode(true);
                    copy.querySelectorAll('br').forEach(br => br.replaceWith(codes.length > 1 ? '' : '\n'));
                    return copy.textContent;
                };
                const body = codes.length ? codes.map(lineText).join('\n') : lineText(node);
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

    function frontMatter(a) {
        const fields = {
            title: a.title,
            author: a.author,
            account: a.account,
            biz: a.biz,
            url: a.url,
            source_url: a.sourceUrl,
            publish_time: a.publishTime ? isoChina(a.publishTime) : '',
            description: a.description,
            cover: a.cover,
            downloaded_at: isoChina(Math.floor(Date.now() / 1000))
        };
        const lines = Object.entries(fields).filter(([, v]) => v).map(([k, v]) => `${k}: ${JSON.stringify(v)}`);
        return `---\n${lines.join('\n')}\n---\n`;
    }

    function render(article) {
        return `${frontMatter(article)}\n# ${article.title}\n\n${htmlToMarkdown(article.contentHtml)}`;
    }

    function safeFilename(name, maxLength = 80) {
        const reserved = /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i;
        let out = (name || '').normalize('NFC')
            .replace(/[<>:"/\\|?*\x00-\x1f]/g, '_')
            .replace(/\s+/g, ' ').trim().replace(/^\.+|\.+$/g, '');
        out = out.slice(0, maxLength).replace(/[ .]+$/, '');
        if (!out) return '未命名';
        return reserved.test(out) ? `_${out}` : out;
    }

    function filename(article) {
        const date = isoChina(article.publishTime || Math.floor(Date.now() / 1000)).slice(0, 10);
        return `${date}_${safeFilename(article.title)}.md`;
    }

    return { htmlToMarkdown, render, filename, safeFilename };
})();
