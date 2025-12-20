// 工具函数（如果需要在前端使用）

// HTML 转 Markdown 的简化版本（用于前端）
function htmlToMarkdownSimple(html) {
  if (!html) return '';

  // 移除脚本和样式
  html = html.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '');
  html = html.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');

  // 转换标题
  html = html.replace(/<h([1-6])[^>]*>(.*?)<\/h\1>/gi, (match, level, text) => {
    return `${'#'.repeat(parseInt(level))} ${text.trim()}\n\n`;
  });

  // 转换图片
  html = html.replace(/<img[^>]+src=["']([^"']+)["'][^>]*alt=["']([^"']*)["'][^>]*>/gi, '![$2]($1)');
  html = html.replace(/<img[^>]+alt=["']([^"']*)["'][^>]+src=["']([^"']+)["'][^>]*>/gi, '![$1]($2)');
  html = html.replace(/<img[^>]+src=["']([^"']+)["'][^>]*>/gi, '![]($1)');

  // 转换链接
  html = html.replace(/<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)<\/a>/gi, '[$2]($1)');

  // 转换粗体和斜体
  html = html.replace(/<strong[^>]*>(.*?)<\/strong>/gi, '**$1**');
  html = html.replace(/<b[^>]*>(.*?)<\/b>/gi, '**$1**');
  html = html.replace(/<em[^>]*>(.*?)<\/em>/gi, '*$1*');
  html = html.replace(/<i[^>]*>(.*?)<\/i>/gi, '*$1*');

  // 转换代码
  html = html.replace(/<pre[^>]*><code[^>]*>(.*?)<\/code><\/pre>/gi, '```\n$1\n```');
  html = html.replace(/<code[^>]*>(.*?)<\/code>/gi, '`$1`');

  // 转换列表
  html = html.replace(/<ul[^>]*>/gi, '');
  html = html.replace(/<\/ul>/gi, '\n');
  html = html.replace(/<ol[^>]*>/gi, '');
  html = html.replace(/<\/ol>/gi, '\n');
  html = html.replace(/<li[^>]*>(.*?)<\/li>/gi, '- $1\n');

  // 转换段落
  html = html.replace(/<p[^>]*>(.*?)<\/p>/gi, '$1\n\n');
  html = html.replace(/<div[^>]*>(.*?)<\/div>/gi, '$1\n');

  // 移除所有剩余的 HTML 标签
  html = html.replace(/<[^>]+>/g, '');

  // 解码 HTML 实体
  const textarea = document.createElement('textarea');
  textarea.innerHTML = html;
  html = textarea.value;

  // 清理多余的换行
  html = html.replace(/\n{3,}/g, '\n\n');
  html = html.trim();

  return html;
}

// 清理文件名
function sanitizeFilename(filename) {
  return filename
    .replace(/[<>:"/\\|?*]/g, '_')
    .replace(/\s+/g, '_')
    .substring(0, 100);
}

// 导出（如果在模块环境中）
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    htmlToMarkdownSimple,
    sanitizeFilename
  };
}

