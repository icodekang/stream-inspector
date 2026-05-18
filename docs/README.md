# Stream Inspector

流媒体调试工具，支持 RTSP / RTSP over TLS / RTSP over HTTP / RTSP over HTTPS 四种取流协议，提供视频实时预览和协议报文调试功能。

## 功能特性

### 协议支持

| URL Scheme | 协议 | 默认端口 | 传输方式 |
|------------|------|---------|----------|
| `rtsp://` | 标准 RTSP (RFC 2326) | 554 | TCP 直连，RTP over TCP (interleaved) |
| `rtsps://` | RTSP over TLS | 322 | TLS 加密直连，RTP over TCP (interleaved) |
| `rtsph://` | RTSP over HTTP | 80 | HTTP 隧道 (GET/POST)，Base64 封装 |
| `rtsphs://` | RTSP over HTTPS | 443 | TLS + HTTP 隧道，Base64 封装 |

### 界面布局

```
┌──────────────────────────────────────────────────┐
│  取流地址: [▼ rtsp://...] [+添加] [管理]        │  ← 控制栏
│  协议: RTSP  │  ● 已连接  [▶ 连接] [■ 断开]    │
├────────────────────┬─────────────────────────────┤
│    视频预览         │    调试信息     [清空] [导出]│
│                    │                             │
│   (实时画面)        │  10:23:45 → OPTIONS ...    │
│                    │  10:23:45 ← 200 OK          │
│                    │  ───────────────────────    │
│                    │  10:23:46 → DESCRIBE ...    │
│                    │  10:23:46 ← 200 OK          │
│                    │  (SDP body)                 │
│                    │  ───────────────────────    │
│                    │  10:23:47 → SETUP ...       │
│                    │  10:23:47 ← 200 OK          │
│                    │  ───────────────────────    │
│                    │  10:23:48 → PLAY ...        │
│                    │  10:23:48 ← 200 OK          │
├────────────────────┴─────────────────────────────┤
│ ● 已连接 │ RTSP │ 1920x1080 H.264/H.265 │ 帧率: 25fps  │  ← 状态栏
└──────────────────────────────────────────────────┘
```

- **视频预览面板（左）**：连接成功后实时渲染视频帧，显示分辨率和编码信息
- **调试信息面板（右）**：彩色高亮显示所有 RTSP/HTTP 协议交互报文
  - 蓝色 →（发送）
  - 绿色 ←（接收）
  - 红色 !!（错误）
  - 灰色时间戳
  - RTP 码流数据自动省略，仅显示 `[RTP interleaved: N bytes]`

### 地址管理

- URL 下拉框支持历史记录，可编辑输入
- **+ 添加** 按钮保存新地址到本地配置文件
- **管理** 按钮打开地址管理弹窗：查看 / 删除 / 新增地址
- 输入 URL 时自动识别协议类型并显示协议名称标签
- 地址持久化存储于 `~/.stream-inspector/addresses.json`

### 调试功能

- 完整记录 RTSP 请求/响应（OPTIONS → DESCRIBE → SETUP → PLAY → TEARDOWN）
- 展示 SDP 描述信息（视频编码、轨道信息）
- RTSP over HTTP/HTTPS 模式下显示 HTTP 隧道建立过程和 Base64 编解码日志
- TLS 模式下显示 TLS 握手状态
- 支持 Digest 认证（自动处理 401 响应并重试）
- **清空** 按钮重置调试面板
- **导出** 按钮将调试日志保存为文本文件

### 视频解码

- RTP 解包：支持 interleaved (TCP) 模式
- H.264 重组：处理 FU-A（分片单元）、STAP-A（聚合单元）、单 NAL 单元
- H.265 重组：处理 FU（分片单元）、AP（聚合单元）、单 NAL 单元
- 解码器：PyAV (FFmpeg) 硬解 H.264/H.265 → RGB24 → QPixmap
- 解码异常自动输出到调试面板，便于排查编码不匹配问题

## 项目架构

```
stream-inspector/
├── main.py                       # 应用程序入口
├── requirements.txt              # Python 依赖清单
├── docs/                         # 项目文档
│   ├── README.md                 # 项目说明（本文件）
│   ├── ARCHITECTURE.md           # 架构设计文档
│   └── DEPLOYMENT.md             # 部署指南
├── src/
│   ├── gui/                      # GUI 层
│   │   ├── main_window.py        # 主窗口 + 深色主题 + 线程管理
│   │   ├── video_panel.py        # 视频预览面板
│   │   ├── debug_panel.py        # 调试信息面板
│   │   └── control_bar.py        # 控制栏 + 地址管理弹窗
│   ├── protocol/                 # 协议层（可扩展）
│   │   ├── base.py               # 抽象基类 StreamProtocol
│   │   ├── rtsp.py               # 标准 RTSP 客户端
│   │   ├── rtsp_tls.py           # RTSP over TLS 客户端
│   │   ├── rtsp_http.py          # RTSP over HTTP 客户端
│   │   ├── rtsp_https.py         # RTSP over HTTPS 客户端
│   │   └── factory.py            # 协议工厂（scheme → 协议类映射）
│   ├── transport/                # 传输层
│   │   ├── connection.py         # TCP/TLS Socket 封装 + 报文拦截
│   │   └── http_tunnel.py        # HTTP 隧道管理（GET/POST）
│   ├── stream/                   # 流处理层
│   │   ├── rtp_parser.py         # RTP 解包 + H.264/H.265 重组
│   │   └── decoder.py            # H.264/H.265 → Qt 帧解码
│   └── debug/                    # 调试层
│       ├── models.py             # 调试数据模型
│       └── logger.py             # 调试日志记录器
```

## 线程模型

```
Main Thread (UI)
    │
    ├── ProtocolWorker (QThread)
    │   ├── 创建协议实例
    │   ├── connect → OPTIONS → DESCRIBE → SETUP → PLAY
    │   ├── receive_loop() 阻塞接收
    │   └── Signal ──→ debug_panel (调试报文)
    │                ──→ video_panel (码流数据)
    │
    └── DecodeWorker (QThread)
        ├── RTP 解包 + H.264/H.265 重组
        ├── PyAV 解码 → QPixmap
        ├── 解码异常自动输出到调试面板
        └── Signal ──→ video_panel (渲染帧)
                       ──→ debug_panel (解码警告/错误)
```

## 扩展指南

新增协议（如 RTMP、SRT、WebRTC）只需三步：

1. 在 `src/protocol/` 下新建文件，继承 `StreamProtocol` 并实现所有抽象方法
2. 在 `src/protocol/factory.py` 的 `PROTOCOL_MAP` 中添加映射：
   ```python
   PROTOCOL_MAP = {
       "rtsp": RtspProtocol,
       "rtsps": RtspOverTlsProtocol,
       "rtsph": RtspOverHttpProtocol,
       "rtsphs": RtspOverHttpsProtocol,
       "rtmp": RtmpProtocol,  # 新增
   }
   ```
3. 若传输层不同（如 RTMP 自定义握手），在 `src/transport/` 下新增对应实现

## 常见问题

### Q: 连接失败 / 超时

检查 URL 格式是否正确（需包含 `://`），服务端是否可达，端口是否正确。

### Q: 视频不显示但有调试信息

检查调试面板中 SETUP 响应是否成功（200 OK），确认视频编码格式为 H.264 或 H.265。若调试面板出现解码器初始化失败或解码异常提示，说明编码格式不兼容或 PyAV/FFmpeg 缺少相应解码器。

### Q: 认证失败

工具支持 Digest 认证，在 URL 中包含用户名密码：
```
rtsp://admin:password@192.168.1.100:554/stream
```

### Q: 深色主题显示异常

确保 PyQt6 >= 6.5.0，如使用旧版本可能需要调整样式表。

## License

本项目仅供学习和调试使用。
