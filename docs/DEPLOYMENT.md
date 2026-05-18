# 部署指南

## 环境要求

| 项目 | 最低要求 | 建议 |
|------|---------|------|
| 操作系统 | Windows 10+ / macOS 11+ / Linux (X11) | Windows 11 |
| Python | 3.10+ | 3.11+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 500 MB | 1 GB (含 FFmpeg 依赖) |

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd stream-inspector
```

### 2. 创建虚拟环境（推荐）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

国内用户可切换镜像源加速：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4. 启动应用

```bash
python main.py
```

## 依赖说明

```
PyQt6>=6.5.0          # Qt GUI 框架，提供界面组件和信号/槽机制
numpy>=1.24.0          # 数值计算库，PyQt6/PyAV 的底层依赖
av>=10.0.0             # PyAV，FFmpeg 的 Python 绑定，用于 H.264/H.265 视频解码
```

`PyQt6` 包含以下自动安装的子包：

| 子包 | 大小 | 说明 |
|------|------|------|
| `PyQt6-Qt6` | ~78 MB | Qt6 运行时库 |
| `PyQt6-sip` | ~53 KB | Python/C++ 绑定生成器 |

## 配置文件

应用启动后自动在用户目录创建配置目录：

```
~/.stream-inspector/
└── addresses.json    # 取流地址列表
```

### addresses.json 格式

```json
{
  "addresses": [
    "rtsp://192.168.1.100:554/stream1",
    "rtsps://192.168.1.100:322/stream2",
    "rtsph://192.168.1.100:8080/stream3",
    "rtsphs://192.168.1.100:443/stream4"
  ]
}
```

## 命令行参数

当前版本不支持命令行参数，所有配置通过 GUI 交互完成。

## 开发环境搭建

### 安装开发依赖

```bash
pip install -r requirements.txt
```

### 目录结构

```
stream-inspector/
├── main.py              # 入口，调试时直接运行
├── requirements.txt
├── docs/                # 项目文档
└── src/                 # 源代码
    ├── gui/             # GUI 相关
    ├── protocol/        # 协议实现
    ├── transport/       # 传输层
    ├── stream/          # 流处理
    └── debug/           # 调试模块
```

### 运行开发模式

直接运行入口文件即可，无需额外构建步骤：

```bash
python main.py
```

### 添加新协议

参见 `docs/ARCHITECTURE.md` 中的「扩展指南」章节。

## 故障排查

### 问题：启动时报 ModuleNotFoundError

**原因**：依赖未安装或版本不兼容。

**解决**：

```bash
# 确认所有依赖已安装
pip list | Select-String "PyQt6|numpy|av"

# 重新安装
pip install --force-reinstall -r requirements.txt
```

### 问题：视频解码报错

**原因**：PyAV 缺少 H.264/H.265 解码器或 FFmpeg 版本问题。

**解决**：

```bash
# 检查 av 是否正常导入
python -c "import av; print(av.codecs_available)" | Select-String "h264|hevc"

# 如没有 h264/hevc 解码器，重新安装 av
pip uninstall av
pip install av --no-cache-dir
```

Windows 上 PyAV 内置了 FFmpeg，无需额外安装。Linux/macOS 可能需要系统安装 FFmpeg：

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg libavcodec-dev libavformat-dev

# Fedora
sudo dnf install ffmpeg ffmpeg-devel
```

### 问题：界面字体显示异常

**原因**：系统缺少等宽字体。

**解决**：调试面板使用 `Consolas` 字体（Windows 自带）。macOS 使用 `Menlo`，Linux 使用 `DejaVu Sans Mono`。

如需自定义字体，修改 `debug_panel.py` 第 49 行：

```python
font = QFont("Consolas", 11)  # 改为系统可用字体
```

### 问题：pip install 超时

**解决**：使用国内镜像

```bash
pip install -r requirements.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --trusted-host pypi.tuna.tsinghua.edu.cn
```

其他可用镜像：
- 阿里云：`https://mirrors.aliyun.com/pypi/simple/`
- 中科大：`https://pypi.mirrors.ustc.edu.cn/simple/`
- 豆瓣：`https://pypi.douban.com/simple/`

### 问题：Linux 下无法启动 GUI

**原因**：缺少 X11 或 Wayland 依赖。

**解决**：

```bash
# Ubuntu/Debian
sudo apt install libxcb-cursor0 libxkbcommon-x11-0

# Fedora
sudo dnf install libxcb xcb-util-cursor libxkbcommon-x11
```

### 问题：macOS 下窗口无法显示

**原因**：macOS 安全策略限制。

**解决**：确保从终端启动（而非双击），或授予终端辅助功能权限。

## 打包部署

### PyInstaller（推荐）

```bash
pip install pyinstaller
pyinstaller --name "StreamInspector" --windowed --onefile --icon=app.ico --add-data "app.ico;." main.py
```

生成的可执行文件在 `dist/StreamInspector.exe` (Windows) 或 `dist/StreamInspector` (macOS/Linux)。

### Nuitka（高性能）

```bash
pip install nuitka
nuitka --standalone --windows-console-mode=disable --output-dir=dist main.py
```

## 版本兼容性

| Python | PyQt6 | 状态 |
|--------|-------|------|
| 3.10 | 6.5.0+ | 支持 |
| 3.11 | 6.6.0+ | 支持 |
| 3.12 | 6.7.0+ | 支持 |
| 3.13 | 6.8.0+ | 支持 |
