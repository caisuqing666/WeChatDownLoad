# 安装问题解决

## 问题：找不到 requirements.txt

如果您在用户主目录（`~`）运行命令，需要先切换到项目目录。

## 解决方法

### 方法一：切换到项目目录（推荐）

```bash
# 切换到项目目录
cd ~/Documents/GitHub/wechatDownload

# 然后安装依赖
pip install -r requirements.txt
```

### 方法二：使用完整路径

```bash
pip install -r ~/Documents/GitHub/wechatDownload/requirements.txt
```

### 方法三：使用 pip3（如果 pip 不可用）

```bash
cd ~/Documents/GitHub/wechatDownload
pip3 install -r requirements.txt
```

## 验证安装

安装完成后，可以运行测试：

```bash
cd ~/Documents/GitHub/wechatDownload
python test_basic.py
```

## 如果仍然遇到问题

### 检查 Python 版本

```bash
python --version
# 或
python3 --version
```

需要 Python 3.7 或更高版本。

### 使用虚拟环境（推荐）

```bash
cd ~/Documents/GitHub/wechatDownload

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 使用国内镜像（如果网络慢）

```bash
cd ~/Documents/GitHub/wechatDownload
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```



