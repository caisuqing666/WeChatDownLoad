#!/bin/bash

# macOS 应用程序修复脚本
# 用于修复 wechatDownload 应用在 macOS 上无法打开的问题

echo "=========================================="
echo "wechatDownload macOS 修复脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 函数：查找应用程序
find_app() {
    local app_name="wechatDownload"
    local possible_locations=(
        "$HOME/Downloads/${app_name}.app"
        "$HOME/Desktop/${app_name}.app"
        "/Applications/${app_name}.app"
        "$HOME/Downloads/wechatDownload*.app"
        "$HOME/Desktop/wechatDownload*.app"
    )
    
    for location in "${possible_locations[@]}"; do
        if [ -e "$location" ]; then
            echo "$location"
            return 0
        fi
    done
    
    # 尝试使用 find 命令搜索
    local found=$(find "$HOME/Downloads" "$HOME/Desktop" "/Applications" -name "*wechatDownload*.app" -type d 2>/dev/null | head -1)
    if [ -n "$found" ]; then
        echo "$found"
        return 0
    fi
    
    return 1
}

# 函数：修复应用程序
fix_app() {
    local app_path="$1"
    
    if [ ! -e "$app_path" ]; then
        echo -e "${RED}错误：找不到应用程序：$app_path${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}找到应用程序：$app_path${NC}"
    echo ""
    
    # 1. 移除隔离属性
    echo "步骤 1: 移除隔离属性..."
    xattr -cr "$app_path" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 隔离属性已移除${NC}"
    else
        echo -e "${YELLOW}⚠ 移除隔离属性时出现警告（可能已经移除）${NC}"
    fi
    echo ""
    
    # 2. 移除特定的隔离标记
    echo "步骤 2: 移除隔离标记..."
    xattr -d com.apple.quarantine "$app_path" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 隔离标记已移除${NC}"
    else
        echo -e "${YELLOW}⚠ 隔离标记可能不存在（这是正常的）${NC}"
    fi
    echo ""
    
    # 3. 设置执行权限
    echo "步骤 3: 设置执行权限..."
    local executable=$(find "$app_path/Contents/MacOS" -type f 2>/dev/null | head -1)
    if [ -n "$executable" ]; then
        chmod +x "$executable"
        echo -e "${GREEN}✓ 执行权限已设置${NC}"
    else
        echo -e "${YELLOW}⚠ 未找到可执行文件（可能不是标准应用结构）${NC}"
    fi
    echo ""
    
    # 4. 检查应用程序架构
    echo "步骤 4: 检查应用程序架构..."
    if [ -n "$executable" ]; then
        local arch=$(file "$executable" 2>/dev/null | grep -o "x86_64\|arm64\|universal")
        local system_arch=$(uname -m)
        
        echo "  应用程序架构: $arch"
        echo "  系统架构: $system_arch"
        
        if [[ "$arch" == *"arm64"* ]] && [[ "$system_arch" == "x86_64" ]]; then
            echo -e "${RED}✗ 警告：这是为 Apple Silicon (M1/M2) 设计的应用，无法在 Intel Mac 上运行${NC}"
            return 1
        elif [[ "$arch" == *"x86_64"* ]] || [[ "$arch" == *"universal"* ]]; then
            echo -e "${GREEN}✓ 架构兼容${NC}"
        fi
    fi
    echo ""
    
    # 5. 验证修复
    echo "步骤 5: 验证修复..."
    if [ -e "$app_path" ]; then
        echo -e "${GREEN}✓ 应用程序文件存在${NC}"
        echo ""
        echo -e "${GREEN}修复完成！${NC}"
        echo ""
        echo "现在可以尝试以下方式打开应用程序："
        echo "1. 双击应用程序图标"
        echo "2. 右键点击 -> 打开"
        echo "3. 如果仍然无法打开，请查看 MACOS_INSTALL.md 获取更多帮助"
        echo ""
        echo "应用程序路径："
        echo "$app_path"
        return 0
    else
        echo -e "${RED}✗ 验证失败：应用程序不存在${NC}"
        return 1
    fi
}

# 主程序
main() {
    echo "正在搜索 wechatDownload 应用程序..."
    echo ""
    
    app_path=$(find_app)
    
    if [ -z "$app_path" ]; then
        echo -e "${RED}未找到 wechatDownload 应用程序！${NC}"
        echo ""
        echo "请确保："
        echo "1. 已从 https://pan.quark.cn/s/09bdfa78d09b 下载 macOS 版本"
        echo "2. 应用程序在以下位置之一："
        echo "   - ~/Downloads/"
        echo "   - ~/Desktop/"
        echo "   - /Applications/"
        echo ""
        echo "或者手动指定应用程序路径："
        read -p "请输入应用程序的完整路径: " app_path
        
        if [ ! -e "$app_path" ]; then
            echo -e "${RED}错误：指定的路径不存在：$app_path${NC}"
            exit 1
        fi
    fi
    
    echo ""
    fix_app "$app_path"
    
    if [ $? -eq 0 ]; then
        echo ""
        read -p "是否现在尝试打开应用程序？(y/n): " open_app
        if [[ "$open_app" == "y" || "$open_app" == "Y" ]]; then
            open "$app_path"
            echo -e "${GREEN}已尝试打开应用程序${NC}"
        fi
    fi
}

# 检查是否以 root 运行
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}警告：不建议以 root 用户运行此脚本${NC}"
    echo "按 Ctrl+C 取消，或按 Enter 继续..."
    read
fi

# 运行主程序
main





