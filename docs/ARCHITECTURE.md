# 架构设计文档

## 整体架构

采用分层架构设计，自下而上分为传输层、协议层、流处理层、GUI 层，各层通过回调和信号/槽进行通信。

```
┌─────────────────────────────────────────────────────────┐
│                     GUI Layer                           │
│  main_window.py  video_panel.py  debug_panel.py        │
│  control_bar.py                                         │
│         ▲  pyqtSignal/pyqtSlot                          │
│         │                                               │
│  ┌──────┴──────┐    ┌──────────────┐                   │
│  │ProtocolWorker│    │ DecodeWorker │  (QThread)       │
│  └──────┬──────┘    └──────┬───────┘                   │
│         │                  │                            │
├─────────┼──────────────────┼────────────────────────────┤
│  Protocol Layer            │  Stream Layer              │
│  base.py rtsp.py           │  rtp_parser.py            │
│  rtsp_http.py              │  decoder.py               │
│  rtsp_https.py             │                            │
│  factory.py                │                            │
│         │                  │                            │
├─────────┼──────────────────┼────────────────────────────┤
│  Transport Layer           │                            │
│  connection.py             │                            │
│  http_tunnel.py            │                            │
│         │                  │                            │
├─────────┼──────────────────┼────────────────────────────┤
│         ▼                  ▼                            │
│              Network (TCP / TLS)                        │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. 传输层 (transport/)

#### connection.py — Connection

底层 TCP/TLS 连接管理器，职责：

- **连接管理**：`connect(host, port, use_tls)` 建立 TCP 或 TLS 连接
- **数据收发**：`send_raw(data)`, `recv_into_buffer(size)`
- **协议消息读取**：
  - `recv_rtsp_message(timeout)` — 读取完整 RTSP 应答（按 `\r\n\r\n` + Content-Length）
  - `recv_interleaved(timeout)` — 读取 `$<channel><2-byte-length><data>` 格式的 Interleaved 数据
  - `recv_message(timeout)` — 自动识别首字节分发到上述两个方法
- **报文拦截**：通过回调函数 (`debug_send_cb`, `debug_recv_cb`, `debug_binary_recv_cb`) 将原始字节流推送给调试层

**设计要点**：
- 使用内部 `bytearray` 缓冲区处理 TCP 粘包/拆包
- 超时机制避免永久阻塞
- Interleaved 识别：首字节 `0x24`(`$`) 为 Interleaved 帧，否则为 RTSP 文本

#### http_tunnel.py — HttpTunnel

HTTP 隧道管理器，职责：

- **隧道建立**：`establish(host, port, path, use_tls)`
  1. 发送 `GET /path HTTP/1.1` 建立 Server→Client 通道
  2. 发送 `POST /path HTTP/1.1` 建立 Client→Server 通道
  3. 使用 `x-sessioncookie` 关联两个通道
- **请求转发**：`send_rtsp(rtsp_message)` — Base64 编码 RTSP 请求并封装到 HTTP POST 中
- **响应接收**：读取 GET 通道中的 Base64 数据，解码为 RTSP 响应
- **HTTP 解析**：支持 Content-Length 和 Chunked Transfer-Encoding

### 2. 协议层 (protocol/)

#### base.py — StreamProtocol (ABC)

抽象基类，定义协议统一接口：

| 抽象方法 | 用途 |
|----------|------|
| `connect()` | 建立传输层连接 |
| `disconnect()` | 断开连接 |
| `describe()` | DESCRIBE 请求，返回 SDP |
| `setup(track_url, rtp_ch, rtcp_ch)` | SETUP 请求，协商传输参数 |
| `play()` | PLAY 请求，开始推流 |
| `teardown()` | TEARDOWN 请求，停止推流 |
| `receive_loop()` | 阻塞循环接收 RTP 数据 |
| `stop()` | 中断接收循环 |

**回调接口**：

```python
debug_callback    # (direction: str, message: str) -> None
video_callback    # (data: bytes) -> None
status_callback   # (status: str) -> None
stream_info_callback  # (info: dict) -> None
```

**辅助方法**：
- `_parse_sdp(sdp)` — 解析 SDP 文本，提取媒体轨道信息
- `_next_cseq()` — 自增 CSeq 序号
- `_build_auth_header(method)` — 构建 Digest 认证头

#### rtsp.py — RtspProtocol

标准 RTSP 协议实现：

- **传输**：通过 `Connection` 对象收发数据
- **认证**：支持 Digest Access Authentication
  - DESCRIBE 收到 `401 Unauthorized` 时，解析 `realm` 和 `nonce`
  - 自动重试并携带 `Authorization` 头
- **步骤**：
  1. `options()` — 查询服务端能力
  2. `describe()` — 获取 SDP 媒体描述
  3. `setup()` — 协商传输参数 `RTP/AVP/TCP;unicast;interleaved=0-1`
  4. `play()` — 请求开始推流 `Range: npt=0.000-`
  5. `receive_loop()` — 循环读取 Interleaved RTP 数据

#### rtsp_http.py — RtspOverHttpProtocol

RTSP over HTTP 协议实现：

- **传输**：通过 `HttpTunnel` 对象收发数据
- **流程**：与标准 RTSP 相同，但每个 RTSP 请求/响应用 Base64 编码封装在 HTTP POST/GET 中
- **调试**：`[Base64]` 前缀标识隧道数据

#### rtsp_https.py — RtspOverHttpsProtocol

RTSP over HTTPS 协议实现：

- 继承 RTSP over HTTP 的所有逻辑
- `connect()` 中通过 `use_tls=True` 建立 TLS 加密连接
- 调试面板记录 TLS 握手状态

#### factory.py — 协议工厂

```python
PROTOCOL_MAP = {
    "rtsp":  RtspProtocol,
    "rtsph": RtspOverHttpProtocol,
    "rtsps": RtspOverHttpsProtocol,
}

def create_protocol(url: str) -> StreamProtocol | None:
    # 解析 URL scheme，查表创建对应协议实例
```

### 3. 流处理层 (stream/)

#### rtp_parser.py — RtpParser

RTP 包解析器，支持 H.264 载荷类型：

- **RTP 头部解析**：Version(2), Padding(1), Extension(1), CSRC Count(4), Marker(1), Payload Type(7), Sequence(16), Timestamp(32), SSRC(32)
- **H.264 NAL 类型识别**：
  - 1-23: 单 NAL 单元
  - 24 (STAP-A): 聚合包，包含多个 NAL 单元
  - 28 (FU-A): 分片单元，需重组
- **FU-A 重组**：
  - `start_bit=1`: 开始累积，记录原始 NAL header
  - 中间分片: 追加数据
  - `end_bit=1`: 输出完整帧并重置状态
- **Annex-B 封装**：每个完整帧前添加 `00 00 00 01` 起始码

#### decoder.py — VideoDecoder

H.264 视频解码器：

- **解码后端**：PyAV (`av.CodecContext`)
- **流程**：
  1. `codec.parse(annexb_data)` — 解析 Annex-B 格式的 H.264 数据
  2. `codec.decode(packet)` — 解码为原始帧
  3. `frame.to_ndarray(format='rgb24')` — 转换为 NumPy 数组
  4. `QImage(data, w, h, bpl, Format_RGB888)` — 封装为 Qt 图像
  5. `QPixmap.fromImage(qimage)` — 可显示的像素图

### 4. GUI 层 (gui/)

#### main_window.py — MainWindow

应用主窗口，负责：

- **布局**：顶部控制栏 + QSplitter 左右分栏 + 底部状态栏
- **深色主题**：`DARK_THEME` 全局 QSS 样式表（配色 `#1a1b2e` / `#252640`）
- **线程管理**：
  - `ProtocolWorker` 在 `QThread` 中运行协议交互
  - `DecodeWorker` 在 `QThread` 中运行视频解码
  - 断开时优雅关闭线程 (`quit()` + `wait(2000)`)
- **信号连接**：
  ```
  ProtocolWorker.debug_message  → debug_panel.append_debug
  ProtocolWorker.video_data     → DecodeWorker.process_data
  DecodeWorker.frame_ready      → video_panel.show_frame
  ProtocolWorker.status_changed → 状态栏更新
  ProtocolWorker.error_occurred → 错误提示
  ProtocolWorker.stream_info    → 视频面板编码信息
  ```

#### video_panel.py — VideoPanel

- 标题栏 + 视频区域 (QLabel) + 底部信息栏
- `show_frame(pixmap)`：缩放并渲染帧
- 状态切换：等待连接 / 连接中 / 连接失败

#### debug_panel.py — DebugPanel

- 标题栏 + QPlainTextEdit + 工具栏（自动滚动、清空、导出）
- 使用 `QTextCharFormat` 实现语法高亮
- 等宽字体 (`Consolas`, 11px)
- 支持导出为 `.txt` 文件

#### control_bar.py — ControlBar

- URL 输入 (QComboBox + editable)
- **+ 添加** 按钮：校验协议 scheme 后保存
- **管理** 按钮：打开 AddressManagerDialog
- 连接状态切换：按钮显隐、地址输入锁定、状态指示器颜色
- `AddressManagerDialog`：QDialog 模态弹窗，支持列表查看、Delete 键删除、新增输入

## 数据流

```
URL 输入 → ControlBar.connect_clicked(url)
    │
    ▼
MainWindow._on_connect(url)
    │
    ├── 创建 ProtocolWorker(url) + QThread
    ├── 创建 DecodeWorker + QThread
    └── 连接信号/槽
    │
    ▼
ProtocolWorker.run()
    │
    ├── create_protocol(url) → 协议实例
    ├── protocol.connect()    → TCP/TLS 连接
    ├── protocol.options()     → 协议调试输出
    ├── protocol.describe()    → SDP (解析视频轨道)
    ├── protocol.setup()       → 协商 RTP/AVP/TCP
    ├── protocol.play()        → 请求推流
    └── protocol.receive_loop()
         │
         ├── 文本消息 → debug_callback → debug_message signal → debug_panel
         └── 二进制帧 → video_callback  → video_data signal    → DecodeWorker
                                                                      │
                                                       RtpParser.parse(data)
                                                       VideoDecoder.decode(frame)
                                                              │
                                                    frame_ready(pixmap) signal
                                                              │
                                                       video_panel.show_frame()
```

## 关键设计决策

### 为什么用回调而非直接继承 QObject

`StreamProtocol` 作为抽象基类 (ABC) 与 `QObject` 存在元类冲突。使用回调函数（`debug_callback`, `video_callback`, `status_callback`）解耦协议实现与 Qt 信号系统，由 `ProtocolWorker` (QObject) 统一转换为 Qt 信号。

### 为什么用 PyAV 而非 OpenCV VideoCapture

- OpenCV 的 `VideoCapture` 不支持直接输入原始 H.264 字节流
- PyAV 提供细粒度控制：`parse()` → `decode()` 分步执行，便于调试
- PyAV 基于 FFmpeg，编解码器支持全面

### 为什么用 TCP Interleaved 而非 UDP 传输

- 防火墙友好（单端口，无需额外开放 UDP 端口范围）
- 简化实现（无需处理 NAT / 多播）
- 适用于调试场景（非生产级延迟要求）
