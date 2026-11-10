// 扩展与命令行版的一致性：同一页面得到相同的 front matter 字段和文件名
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { JSDOM } = require('jsdom');

const { window } = new JSDOM('');
globalThis.DOMParser = window.DOMParser;
globalThis.Node = window.Node;

const WeChatMarkdown = require('../../chrome_extension/markdown.js');

const ROOT = path.resolve(__dirname, '../..');
const EXTRACT = fs.readFileSync(path.join(ROOT, 'chrome_extension/extract.js'), 'utf8');
const PYTHON = process.env.PYTHON || 'python3';
const REQUEST_URL = 'https://mp.weixin.qq.com/s/fixture';

const PAGES = [
    'tests/fixtures/article.html',
    'tests/fixtures/real/ruanyifeng-ai-workflow.html',
    'tests/fixtures/real/python-wechat-backend.html',
    'tests/fixtures/real/weixin-reputation-guide.html'
];

function extract(file) {
    const dom = new JSDOM(fs.readFileSync(path.join(ROOT, file), 'utf8'), { url: REQUEST_URL, runScripts: 'outside-only' });
    return dom.window.eval(`${EXTRACT}\nextractWeChatArticle()`);
}

function reference(file) {
    const out = execFileSync(PYTHON, [path.join(__dirname, 'python_reference.py'), path.join(ROOT, file), REQUEST_URL]);
    return JSON.parse(out.toString('utf8'));
}

function parseFrontMatter(text) {
    const lines = text.split('\n');
    assert.equal(lines[0], '---');
    const fields = {};
    for (const line of lines.slice(1, lines.indexOf('---', 1))) {
        const i = line.indexOf(': ');
        fields[line.slice(0, i)] = JSON.parse(line.slice(i + 2));
    }
    delete fields.downloaded_at;
    return fields;
}

for (const file of PAGES) {
    test(`与命令行版一致：${path.basename(file)}`, async () => {
        const article = extract(file);
        assert.ok(!article.error, article.error);
        const expected = reference(file);
        assert.deepEqual(parseFrontMatter(WeChatMarkdown.frontMatter(article)), expected.fields);
        assert.equal(await WeChatMarkdown.filename(article), `${expected.stem}.md`);
        assert.equal(article.account, expected.account);
    });
}

test('验证页给出提示而不是生成文件', () => {
    const result = extract('tests/fixtures/real/verify.html');
    assert.match(result.error, /验证/);
});
