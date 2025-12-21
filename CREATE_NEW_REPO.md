# 创建新 GitHub 仓库指南

## 方法一：使用 GitHub 网站（推荐）

### 步骤 1: 在 GitHub 上创建新仓库

1. **登录 GitHub**
   - 访问：https://github.com
   - 使用您的账户 `caisuqing666` 登录

2. **创建新仓库**
   - 点击右上角的 "+" 图标
   - 选择 "New repository"

3. **填写仓库信息**
   - **Repository name**: `wechatDownload`（或您喜欢的名称）
   - **Description**: `微信公众号文章下载工具 - Python版本和Chrome扩展版本`
   - **Visibility**: 
     - Public（公开，推荐）
     - Private（私有）
   - **重要**: 
     - ❌ 不要勾选 "Add a README file"
     - ❌ 不要添加 .gitignore
     - ❌ 不要添加 license
   - 点击 "Create repository"

### 步骤 2: 连接本地仓库并推送

创建仓库后，GitHub 会显示推送命令。或者运行以下命令：

```bash
cd ~/Documents/GitHub/wechatDownload

# 更新远程地址（替换为您的仓库名）
git remote set-url origin https://github.com/caisuqing666/wechatDownload.git

# 推送代码
git push -u origin main
```

## 方法二：使用 GitHub CLI（如果已安装）

如果您安装了 GitHub CLI (`gh`)，可以直接在命令行创建：

```bash
# 登录 GitHub CLI（如果还没登录）
gh auth login

# 创建新仓库并推送
cd ~/Documents/GitHub/wechatDownload
gh repo create wechatDownload --public --source=. --remote=origin --push
```

## 方法三：使用脚本自动创建

我可以为您创建一个自动化脚本，但需要您先完成 GitHub 网站上的创建步骤。

## 推荐仓库设置

- **仓库名**: `wechatDownload` 或 `wechat-downloader`
- **描述**: `微信公众号文章批量下载工具 - 支持Python和Chrome扩展`
- **可见性**: Public（公开，方便分享）
- **Topics**: 
  - `wechat`
  - `python`
  - `chrome-extension`
  - `article-downloader`
  - `markdown`

## 创建后的操作

1. **添加仓库描述和 Topics**
2. **查看 README.md**（会自动显示）
3. **添加 LICENSE**（如果需要）
4. **设置 GitHub Pages**（如果需要展示文档）

## 需要帮助？

告诉我：
1. 您想使用的仓库名称
2. 是否要设置为 Public 或 Private
3. 我帮您生成具体的命令


