# StudyFloat — 极简独立视频悬浮播放器 设计规格

- 日期：2026-11-19
- 状态：设计已获用户批准，进入实现计划阶段
- 范围：P0（MVP）。P1/P2 仅记录为未来方向，不在本轮实现。

## 1. 背景与目标

在 Bilibili 等网站观看课程时，网页包含大量干扰元素。浏览器原生画中画的控制能力与自定义程度有限。StudyFloat 的目标是把视频从浏览器中提取出来，在 Windows 桌面上以一个独立、极简、低占用、可自由调整尺寸与置顶的窗口播放。

核心成功标准（唯一判断）：

> 用户能否从 Bilibili 获取一个视频，并将其转换为独立于浏览器运行的极简桌面视频窗口；该窗口能够自由调整大小、置顶、隐藏控制栏，并在浏览器最小化后持续播放，同时保持足够低的桌面空间占用和视觉干扰。

## 2. 已确认的决策

| 决策项 | 结论 | 理由 |
|---|---|---|
| 技术栈 | Python 3.12 + PySide6 启动器 → yt-dlp（库模式）解析 → 独立 `mpv.exe` 进程 + JSON IPC（Windows 命名管道） | 唯一同时满足“真正独立窗口、浏览器关闭后仍播放、低占用、精确播放控制、易打包”的方案 |
| B站解析范围 | 免登录公开流为主；**支持用户自带 Cookie 文件**（Netscape 格式）解锁用户自身有权限的清晰度/规避 412 | 用户明确选择；Cookie 由用户提供，不绕过平台权限 |
| 控制层 | mpv 内建 OSC/Lua（hover 自动显示） | 与视频窗口一体，无额外窗口，闪烁/错位风险最低 |
| 交付形态 | 免安装绿色版（PyInstaller `--onedir` 文件夹） | 用户明确选择；最易分发运行 |
| 播放器形态 | mpv 作为**独立进程**，非内嵌 libmpv | 内嵌方案在启动器关闭时会中断播放，违背核心目标 |

## 3. 技术选型说明

### 3.1 方案对比

| 方案 | 独立窗口 | 播放控制 | 打包体积 | 浏览器关闭后存活 | 结论 |
|---|---|---|---|---|---|
| A. Electron / Tauri + `<video>` | 需自行构建管理 | 受限于浏览器能力 | 大（Node/WebView） | 需额外设计 | 否决 |
| B. Python + 内嵌 libmpv | 否（依附启动器窗口） | 良好 | 中 | **否** | 否决（违背核心目标） |
| C. Python 启动器 + 独立 mpv.exe + IPC ✅ | 原生独立窗口 | 精确（JSON IPC 全属性） | 小（约 80MB 绿色文件夹） | **是** | 采用 |

### 3.2 关键组件

- **yt-dlp**（库模式 `extract_info(download=False)`）：解析 BV URL 为 DASH 视频流 + 音频流直链；内部处理 WBI 签名；`--cookiefile` 支持用户 Cookie。注意：签名直链数小时后过期，必须每次播放时重新解析，不可缓存。
- **mpv.exe**（独立进程）：真正独立 OS 窗口；`--border=no --ontop --keepaspect=yes --hwdec=auto-safe --force-window=yes --idle=yes --no-config`；内建 OSC 提供悬停控制层；硬解降低 CPU。
- **JSON IPC over Windows 命名管道**：`--input-ipc-server=\\.\pipe\studyfloat_<id>`；命令如 `loadfile`、`audio-add`、`set pause`、`seek`、`set speed`、`set volume`、`observe_property`、`get_property geometry`。
- **PySide6**：仅用于极简启动器/设置窗口；`QProcess` 管理 mpv 子进程；`QSettings`/JSON 持久化设置。LGPL 许可，PyInstaller 官方收集钩子。
- **PyInstaller `--onedir`**：打包为绿色文件夹；需 `--collect-all PySide6 --collect-all yt_dlp`，并确保 mpv.exe 与全部 DLL 同目录。

## 4. 架构与模块

```
StudyFloat/
├── app/
│   ├── main.py                  # 启动入口
│   ├── ui/
│   │   ├── launcher.py          # URL 输入、播放按钮、设置入口、错误提示
│   │   └── settings_dialog.py   # 基础设置（Cookie 路径、默认倍速、音量、窗口预设）
│   ├── source/
│   │   ├── url_validator.py     # Bilibili URL / BV 号基础校验
│   │   └── bilibili_parser.py   # yt-dlp 封装：extract_info → 选流 → StreamInfo
│   ├── player/
│   │   ├── mpv_controller.py    # 启动 mpv 进程、命名管道 IPC、命令封装、属性订阅
│   │   └── osc.lua              # 自定义极简控制层脚本（随 mpv 分发）
│   ├── window/
│   │   └── geometry.py          # 读/写 geometry 属性，预设尺寸，位置与尺寸记忆
│   └── config.py                # 设置读写（QSettings 或 JSON）
├── resources/                   # 打包用 mpv.exe + DLL、osc.lua、input.conf
├── docs/superpowers/specs/      # 本设计文档
├── build.spec / build 脚本      # PyInstaller 配置
└── README / 使用说明 / 快捷键说明
```

### 4.1 数据流

1. 用户在启动器输入/粘贴 Bilibili URL（或 BV 号）→ `url_validator` 校验并规范化为完整 URL。
2. `bilibili_parser` 调用 yt-dlp `extract_info(download=False)`（可选 Cookie）→ 得到 `StreamInfo(video_url, audio_url?, title, duration)`。优先选“音视频合并”格式；仅 DASH 时选最佳 video-only + audio-only，用 mpv `audio-add <url> external` 加载音轨。
3. `mpv_controller` 以独立进程启动 mpv（含 IPC 管道、无边框、置顶、几何、硬解参数），随后 `loadfile` + 可选 `audio-add` + `set pause false`。
4. 启动器可隐藏/最小化；mpv 作为独立进程继续播放。
5. 播放控制：设置界面/快捷键经 IPC 下发命令；`observe_property` 同步 time-pos、pause、speed、volume、geometry。
6. 关闭 mpv 或窗口时，`geometry.py` 保存窗口位置与尺寸到配置。

### 4.2 模块边界

- `source` 只依赖 yt-dlp，不依赖 UI 或 mpv；解析器与播放解耦（需求 4.1）。
- `player` 只依赖 mpv IPC 协议；不解析 URL。
- `window` 只负责几何属性读写与预设。
- `config` 是唯一持久化入口。

## 5. 功能需求（P0 范围）

### 5.1 视频源
- 完整 Bilibili 链接、BV 号、粘贴 URL、基础校验。
- 解析失败给出简洁错误提示（见 §7）。
- 支持重新解析。
- 可选 Cookie 文件：用户在设置中指定 Netscape 格式 cookie.txt，解析器透传给 yt-dlp `cookiefile`。

### 5.2 独立窗口
- 真正独立桌面窗口；浏览器最小化/切标签/关闭后继续播放。
- 无边框、无标题栏；视频填充并保持比例不拉伸。
- 自由移动、自由缩放；`--keepaspect=yes` 保持比例。
- Windows 多显示器（geometry 传绝对坐标）。

### 5.3 低占用与窗口样式
- 预设尺寸：微型 320×180、小型 400×225、标准 480×270（默认）、大型 640×360、自定义。
- 无边框 / 恢复边框切换；置顶 / 取消置顶切换。
- 位置与尺寸记忆（`geometry` 属性持久化）。
- 默认隐藏控制层。

### 5.4 播放控制
- 播放/暂停、进度拖动、快退/快进（±5s）、音量、静音、倍速、全屏、退出。
- 倍速：0.5/0.75/1.0/1.25/1.5/1.75/2.0（可调；自定义留 P1）。
- 快捷键（P0 用 mpv `input.conf` 实现，P1 再做可视化自定义）：Space 播放暂停、←/→ ±5s、↑/↓ 音量、M 静音、[ / ] 降/升速、F 全屏、Esc 退出全屏。

### 5.5 自动隐藏控制层
- 默认仅显示画面；鼠标移动进入时 OSC `auto` 模式显示简洁控制条；静止约 1.5–3 秒后隐藏；不闪烁；不影响播放。
- 通过随包分发的 `osc.lua`（极简样式）与 `input.conf` 实现。

## 6. UI 设计

- 启动器极简：标题 StudyFloat、URL 输入框、[播放] 按钮、设置入口、（可选）最近播放。布局按需求文档 5.2 示例。
- 播放成功后，P0 将启动器窗口最小化（不依赖浏览器）；系统托盘常驻属 P1。
- 视频窗口默认纯画面；悬停显示底部半透明黑色控制条（播放/暂停、进度、时间、倍速、音量）。
- P0 右键交互：通过随包 `input.conf` 将鼠标右键绑定为显示 mpv 内建统计/菜单，并通过快捷键（§5.4）+ 启动器设置提供等价操作（播放/暂停、置顶、无边框、倍速、音量、静音、关闭）。功能完整的自定义右键菜单延后到 P1（见 §12）。

## 7. 错误与边界处理

统一原则：错误提示简洁可理解，不向用户展示开发堆栈。

| 场景 | 处理 |
|---|---|
| URL 无效 / BV 号格式错误 | 输入框下方提示“链接格式不正确”，不发起解析 |
| 视频已删除 / 需登录 / 权限不足 | 解析失败提示“无法访问该视频：可能需要登录或视频已删除”，可引导设置 Cookie |
| Cookie 失效 / 412 | 提示“访问被平台拒绝，请更新 Cookie 或稍后重试”，带重试按钮 |
| 网络中断 | 提示“网络连接失败，请检查网络后重试” |
| 播放器启动失败 | 提示“播放窗口启动失败”，附“重试/关闭” |
| 视频流过期（播放中） | 检测播放错误 → 自动重新解析并 `loadfile` 重载一次；失败则提示 |
| 不支持编码 / 音画不同步 | 优先选合并格式；DASH 用 `audio-add`；失败给出简洁提示 |
| 播放中窗口关闭 | 正常退出，保存 geometry，无报错 |
| 多个窗口同时运行 | 每个 mpv 管道用唯一 ID（`studyfloat_<uuid前8>`），互不干扰 |

## 8. 技术验证（必须在完整 MVP 前完成）

按需求第 9 节，先完成 A/B/C 三项验证，三项通过后才正式开发完整 UI。

### 验证 A：Bilibili 解析
- `py -m pip install -U yt-dlp`
- `yt-dlp -j --no-warnings "<公开 BV URL>"`，确认 `formats[]` 含带 `url` 的 DASH/合并格式。
- Python `extract_info(download=False)` 取得可播放直链；验证一个真实公开视频。
- 通过标准：拿到可播放直链；失败可复现并给出错误分类。

### 验证 B：独立窗口
- 用直链启动：`mpv.exe --no-config --idle=yes --force-window=yes --border=no --ontop --keepaspect=yes --geometry=480x270+100+100 --hwdec=auto-safe --input-ipc-server=\\.\pipe\studyfloat_test "<url>"`。
- 关闭/最小化浏览器后确认 mpv 窗口仍在播放。
- 通过标准：视频独立播放，不依赖浏览器 UI。

### 验证 C：窗口与播放控制
- 通过命名管道发送 JSON：`loadfile`、`audio-add`、`set pause`、`seek`、`set speed`、`set volume`、`observe_property`、`get_property geometry`。
- 确认无边框/置顶/拖动/缩放生效，倍速与进度控制生效。
- 通过标准：所有命令有正确 `error` 返回，`observe_property` 收到 `time-pos` 事件。

## 9. 验收测试（对齐需求第 12 节）

- 视频：有效链接解析、播放、暂停、进度拖动、快进/快退、倍速、音量/静音。
- 窗口：独立于浏览器；浏览器最小化/切标签不影响；无边框；置顶；自由缩放/拖动；画面不变形。
- UI：默认仅画面；控制层默认隐藏；悬停显示、离开自动隐藏；低占用窗口可观看；无明显闪烁；操作响应正常。
- 打包：Windows 直接运行；无需开发环境；依赖齐全；绿色文件夹可直接启动。

## 10. 交付清单

- 完整源码与目录结构；技术选型说明；依赖列表。
- 免安装绿色版（PyInstaller `--onedir` 文件夹，含 mpv.exe/DLL/osc.lua/input.conf、yt-dlp）。
- 安装/使用说明、配置说明、快捷键说明。
- 已完成功能清单、未完成功能清单（P1/P2）、已知问题、后续开发建议。

## 11. 已知风险与缓解

1. **B站反爬/API 变更（最高）**：412、WBI 变更、清晰度登录门槛 → 保持 yt-dlp 更新；可选 Cookie；重试与退避；清晰错误提示。
2. **直链过期**：每次播放重新解析，不缓存 URL；播放中失败自动重载一次。
3. **DASH 音画同步**：优先合并格式；DASH 用 `audio-add` 外挂音轨；实测验证。
4. **mpv 打包**：DLL/插件缺失 → 保持目录结构，`--no-config`，干净环境验证；Qt 插件由 `--collect-all` 收集。
5. **杀毒误报**：PyInstaller 与 mpv.exe 可能误报 → 文档说明加白名单，后续可签名。
6. **无边框窗口拖动**：需在 mpv Lua/input.conf 中实现鼠标拖动（P0 必须解决，否则“自由移动”不达标）。
7. **多显示器/高 DPI**：geometry 绝对坐标；P0 做基本支持，P1 优化。

## 12. 不在本轮范围（P1/P2 仅记录）

Cookie 自动管理、清晰度切换、播放历史、快捷键可视化配置、多视频窗口、系统托盘（P1）；浏览器插件、YouTube、字幕、主题等（P2）。需求第 8 节列出的禁止项（账号系统、社交、AI 分析等）一律不做。

## 13. 参考资料

- mpv 手册（JSON IPC、窗口选项、OSC）：https://mpv.io/manual/stable/
- mpv JSON IPC：https://raw.githubusercontent.com/mpv-player/mpv/master/DOCS/man/ipc.rst
- yt-dlp 元数据指南（直链与过期）：https://ytdlp.org/guides/get-video-metadata
- yt-dlp B站免登录高清 PR：https://github.com/yt-dlp/yt-dlp/pull/10559
- yt-dlp 412 修复 PR：https://github.com/yt-dlp/yt-dlp/pull/16889
- Bilibili 流地址 API 参考：https://github.com/socialsisteryi/bilibili-api-collect/blob/master/docs/video/videostream_url.md
- Qt/PyInstaller 部署：https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html
