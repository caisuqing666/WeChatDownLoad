# 创建 GitHub 仓库步骤

## 第一步：在 GitHub 上创建仓库

1. **打开浏览器，访问 GitHub**
   - 网址：https://github.com
   - 登录您的账户（caisuqing666）

2. **创建新仓库**
   - 点击右上角的 "+" 图标
   - 选择 "New repository"

3. **填写仓库信息**
   - **Repository name**: `wechatDownload`
   - **Description**: `微信公众号文章批量下载工具 - Python版本和Chrome扩展版本`
   - **Visibility**: 
     - 选择 **Public**（公开，推荐）
     - 或 **Private**（私有，仅您可见）
   - **重要**：不要勾选以下选项：
     - ❌ Add a README file
     - ❌ Add .gitignore
     - ❌ Choose a license
   - 保持仓库为空

4. **点击 "Create repository"**

## 第二步：推送代码

创建仓库后，在终端运行：

```bash
cd ~/Documents/GitHub/wechatDownload
git push -u origin main
```

## 如果遇到认证问题

如果提示需要登录，可以：

### 方法一：使用 Personal Access Token

1. **创建 Token**
   - GitHub → Settings → Developer settings
   - Personal access tokens → Tokens (classic)
   - Generate new token (classic)
   - 选择权限：`repo`（全部勾选）
   - 生成并复制 token

2. **使用 token 推送**
   ```bash
   git push https://您的token@github.com/caisuqing666/wechatDownload.git main
   ```

### 方法二：使用 GitHub CLI

```bash
# 安装 GitHub CLI（如果还没有）
brew install gh

# 登录
gh auth login

# 推送
git push -u origin main
```

## 快速命令

创建仓库后，直接运行：

```bash
cd ~/Documents/GitHub/wechatDownload
git push -u origin main
```

## 验证

推送成功后，访问：
https://github.com/caisuqing666/wechatDownload

应该能看到所有文件。

