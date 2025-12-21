# 安装指南

## 快速安装

### 1. 确保已安装 Python

检查 Python 版本（需要 3.7 或更高）：

```bash
python --version
# 或
python3 --version
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

或者使用 pip3：

```bash
pip3 install -r requirements.txt
```

### 3. 验证安装

运行测试脚本：

```bash
python test_basic.py
```

如果所有测试通过，说明安装成功。

## 可选依赖

### 剪贴板支持（macOS/Windows）

如果需要从剪贴板读取 token：

```bash
pip install pyperclip
```

注意：Linux 系统需要额外配置，详见 pyperclip 文档。

## 开发模式安装

如果需要修改代码，可以使用开发模式安装：

```bash
pip install -e .
```

## 常见问题

### Q: pip 命令不存在

A: 可能需要使用 `pip3` 或 `python -m pip`：

```bash
python3 -m pip install -r requirements.txt
```

### Q: 权限错误

A: 使用用户安装模式：

```bash
pip install --user -r requirements.txt
```

### Q: 网络问题

A: 使用国内镜像源：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 下一步

安装完成后，查看 [QUICKSTART.md](QUICKSTART.md) 开始使用。





