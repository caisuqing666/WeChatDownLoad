# GitHub 上传指南

## 当前状态

✅ **本地提交已完成**
- 所有文件已提交到本地仓库
- 提交信息：添加Python版本和Chrome扩展版本

❌ **推送到 GitHub 失败**
- 错误：权限被拒绝（Permission denied）
- 原因：当前 Git 用户 `caisuqing666` 没有 `qiye45/wechatDownload` 仓库的写入权限

## 解决方案

### 方案一：Fork 仓库到自己的账户（推荐）

如果您没有原仓库的写入权限，可以：

1. **Fork 仓库**
   - 访问：https://github.com/qiye45/wechatDownload
   - 点击右上角的 "Fork" 按钮
   - 这会创建一个属于您的副本

2. **更新远程仓库地址**
   ```bash
   cd ~/Documents/GitHub/wechatDownload
   git remote set-url origin https://github.com/您的用户名/wechatDownload.git
   ```

3. **推送到您的仓库**
   ```bash
   git push origin main
   ```

### 方案二：创建新仓库

1. **在 GitHub 上创建新仓库**
   - 登录 GitHub
   - 点击右上角 "+" → "New repository"
   - 输入仓库名称（如：`wechatDownload`）
   - 选择 Public 或 Private
   - **不要**初始化 README、.gitignore 或 license

2. **更新远程仓库地址**
   ```bash
   cd ~/Documents/GitHub/wechatDownload
   git remote set-url origin https://github.com/您的用户名/wechatDownload.git
   ```

3. **推送到新仓库**
   ```bash
   git push -u origin main
   ```

### 方案三：使用 SSH 密钥（如果有权限）

如果您有原仓库的写入权限，可以配置 SSH：

1. **检查是否有 SSH 密钥**
   ```bash
   ls -la ~/.ssh/id_rsa.pub
   ```

2. **如果没有，生成 SSH 密钥**
   ```bash
   ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
   ```

3. **添加 SSH 密钥到 GitHub**
   - 复制公钥：`cat ~/.ssh/id_rsa.pub`
   - 在 GitHub → Settings → SSH and GPG keys → New SSH key

4. **更新远程地址为 SSH**
   ```bash
   git remote set-url origin git@github.com:qiye45/wechatDownload.git
   ```

5. **推送**
   ```bash
   git push origin main
   ```

### 方案四：使用 Personal Access Token

1. **创建 Personal Access Token**
   - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - 点击 "Generate new token"
   - 选择权限：`repo`
   - 复制生成的 token

2. **使用 token 推送**
   ```bash
   git push https://您的token@github.com/qiye45/wechatDownload.git main
   ```

## 当前提交内容

已提交的文件包括：

- ✅ Python 版本（wechat_downloader 模块）
- ✅ Chrome 扩展版本
- ✅ 完整的文档和使用指南
- ✅ 示例文件和使用脚本
- ✅ 配置文件（requirements.txt, setup.py）
- ✅ .gitignore 文件

## 推荐操作

**最简单的方法**：Fork 原仓库到您的账户

1. 访问 https://github.com/qiye45/wechatDownload
2. 点击 "Fork" 按钮
3. 运行以下命令：
   ```bash
   cd ~/Documents/GitHub/wechatDownload
   git remote set-url origin https://github.com/您的GitHub用户名/wechatDownload.git
   git push origin main
   ```

## 验证上传

上传成功后，访问您的 GitHub 仓库页面，应该能看到所有文件。

## 需要帮助？

如果遇到问题，请告诉我：
1. 您的 GitHub 用户名
2. 您是否有原仓库的写入权限
3. 您希望使用哪种方案


