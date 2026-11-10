const test = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');

const { window } = new JSDOM('');
globalThis.DOMParser = window.DOMParser;
globalThis.Node = window.Node;

const { htmlToMarkdown } = require('../../chrome_extension/markdown.js');

test('多个 <code>：<br> 转换行，行尾占位 <br> 只去掉一个', () => {
    const html = '<pre data-lang="js">'
        + '<code>a<br>b</code>'
        + '<code>c<br></code>'
        + '<code><br></code>'
        + '<code>d<br><br></code>'
        + '<code>e</code>'
        + '</pre>';
    assert.equal(htmlToMarkdown(html), '```js\na\nb\nc\n\nd\n\ne\n```\n');
});

test('单个 <code>：<br> 全部转换行，语言只取 <pre data-lang>', () => {
    const html = '<pre data-lang="python"><code class="language-py">x = 1<br>y = 2<br><br>print(x)<br></code></pre>';
    assert.equal(htmlToMarkdown(html), '```python\nx = 1\ny = 2\n\nprint(x)\n```\n');
});

test('没有 <code> 的 <pre>：直接取 <pre> 文本，<br> 转换行', () => {
    const html = '<pre>line1<br>line2<br>  indented</pre>';
    assert.equal(htmlToMarkdown(html), '```\nline1\nline2\n  indented\n```\n');
});

test('代码块里的 Markdown 符号不转义', () => {
    const html = '<pre><code>return "*not italic*"</code></pre>';
    assert.equal(htmlToMarkdown(html), '```\nreturn "*not italic*"\n```\n');
});
