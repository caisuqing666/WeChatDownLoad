# 创建新 GitHub 仓库 - 详细步骤

## 📋 快速步骤

### 1. 在 GitHub 网站创建仓库

1. 访问：https://github.com/new
2. 填写信息：
   - **Repository name**: `wechatDownload`（或您喜欢的名称）
   - **Description**: `微信公众号文章下载工具 - Python版本和Chrome扩展`
   - **Visibility**: 选择 Public 或 Private
   - **重要**: 不要勾选任何初始化选项（README、.gitignore、license）
3. 点击 **"Create repository"**

### 2. 连接本地仓库

创建完成后，在终端运行：

```bash
cd ~/Documents/GitHub/wechatDownload

# 移除旧的远程仓库（如果存在）
git remote remove origin

# 添加新的远程仓库（替换为您的仓库名）
git remote add origin https://github.com/caisuqing666/wechatDownload.git

# 推送代码
git push -u origin main
```

## 🎯 完整命令（复制粘贴）

```bash
cd ~/Documents/GitHub/wechatDownload
git remote remove origin
git remote add origin https://github.com/caisuqing666/wechatDownload.git
git push -u origin main
```

**注意**: 将 `wechatDownload` 替换为您在 GitHub 上创建的实际仓库名称。

## ✅ 验证

推送成功后，访问您的仓库：
```
https://github.com/caisuqing666/wechatDownload
```

应该能看到所有文件。

## 🔧 如果遇到问题

### 问题：仓库已存在

如果仓库名称已存在，可以：
1. 使用不同的名称（如：`wechat-downloader`）
2. 或删除旧仓库后重新创建

### 问题：需要认证

如果提示需要登录：
1. 使用 Personal Access Token
2. 或配置 SSH 密钥

## 📝 仓库推荐设置

创建后建议添加：

- **Description**: `微信公众号文章批量下载工具 - 支持Python命令行和Chrome浏览器扩展`
- **Topics**: 
  - `wechat`
  - `python`
  - `chrome-extension`
  - `article-downloader`
  - `markdown`
  - `web-scraping`
