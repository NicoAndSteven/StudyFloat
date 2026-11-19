# StudyFloat

极简独立视频悬浮播放器 —— 把 Bilibili 视频从浏览器中提取出来，在 Windows 桌面上以一个**独立、无边框、可置顶、可自由缩放**的窗口播放。浏览器最小化甚至关闭后，视频仍在桌面窗口继续播放。

## 项目状态

**P0（MVP）已完成并打包为免安装绿色版。**

- 技术验证 A（解析）/ B（独立窗口）/ C（IPC 控制）全部通过
- 端到端实测：解析 → 独立 mpv 播窗 → 分离音频 → 倍速 / 跳转 / 静音 → 关闭，全链路通过
- **47 个自动化测试全部通过**（`pytest tests -q`）
- 扫码登录、合辑分P选择均已实测
- 当前可用绿色版：`dist/StudyFloat_v4/StudyFloat_v4.exe`（约 217MB）

> 严格遵循：只用真实 mpv 进程播放真实视频直链，绝无静态界面冒充播放、绝无模拟数据。

## 核心特性

- **真正独立的播放器**：播放走独立 `mpv.exe` 进程，不是浏览器画中画，也不是内嵌控件。启动器关闭、浏览器关闭后播放不中断。
- **极简低干扰窗口**：无边框、无标题栏，保持视频比例；可拖动、可缩放；控制条（mpv 内建 OSC）默认悬停显示、约 2 秒自动隐藏。
- **深色现代 UI**：启动器、分P选择、扫码登录、设置窗口统一深色现代风格（渐变蓝点缀、圆角卡片），启动器为自绘无边框窗口。
- **置顶与尺寸记忆**：默认置顶；四档尺寸预设（微型 / 小型 / 标准 / 大型）；窗口位置尺寸自动记忆。
- **扫码登录**：启动器内扫码，登录态自动保存到程序目录，无需手动导出 / 粘贴 Cookie，也不读取浏览器加密 Cookie。
- **合辑（多P）支持**：粘贴课程合辑链接（无论是否带 `p=N`）都会弹出深色分P列表供选择，链接里原有的分P会默认高亮。
- **用户自带 Cookie**：可选，在设置中指定 Netscape 格式 `cookies.txt`，作为扫码登录态的回退。

## 技术选型

| 组件 | 选型 | 理由 |
|---|---|---|
| 启动器 UI | Python 3.12 + PySide6 | 极简界面足够；打包成熟；LGPL 许可 |
| 视频解析 | yt-dlp（库模式） | 支持 B站 DASH 直链、WBI 签名、可选 Cookie |
| 播放引擎 | 独立 `mpv.exe` 进程 | 真正独立窗口；浏览器/启动器关闭后仍播放；硬解低占用；JSON IPC 精确控制 |
| IPC | Windows 命名管道 + 换行 JSON（同步请求/响应） | 避免后台读线程与管道关闭竞争导致的死锁（见已知问题） |
| 控制层 | mpv 内建 OSC/Lua | 与视频窗口一体，悬停显示、静止隐藏，无额外窗口 |
| 扫码登录 | B站官方 passport 接口 + curl_cffi | 不经浏览器 Cookie，规避 Chrome 127+ App-Bound Encryption |
| 分P列表 | B站官方 `view` API | 一次取回全部分P元数据（154P 实测 0.35 秒），不逐个枚举 |
| 打包 | PyInstaller `--onedir` | 免安装绿色文件夹，无需 Python 环境 |

设计文档：[设计规格](docs/superpowers/specs/2026-11-19-studyfloat-design.md)；实现计划：[P0 计划](docs/superpowers/plans/2026-11-19-studyfloat-p0.md)；验证过程：[验证记录](docs/验证记录.md)。

## 目录结构

```
app/
├── main.py                      # 入口：输入 → 选P → 解析 → 启动 mpv
├── config.py                    # 设置持久化（config.json）
├── source/
│   ├── url_validator.py         # 链接校验与规范化（保留 ?p=N）
│   ├── bilibili_parser.py       # yt-dlp 解析 → StreamInfo
│   ├── bilibili_parts.py        # 官方 view API 拉取分P列表
│   └── bili_login.py            # 官方 passport 扫码登录 + Netscape Cookie 写出
├── player/
│   ├── mpv_controller.py        # mpv 子进程 + 命名管道同步 IPC
│   ├── errors.py                # 用户可见异常类型
│   └── resources/
│       ├── studyfloat.lua       # 极简 OSC 配置
│       └── input.conf           # 快捷键绑定
├── ui/
│   ├── launcher.py              # 启动器（播放 / 设置 / 扫码登录）
│   ├── settings_dialog.py       # 设置窗口
│   ├── qr_login_dialog.py       # 扫码登录窗口（QPainter 绘制二维码）
│   └── part_picker_dialog.py    # 分P选择窗口
└── window/geometry.py           # 窗口几何预设与记忆
tools/
├── fetch_mpv.py                 # 下载便携版 mpv（BCJ2 回退解压）
├── parse_probe.py               # 验证 A：解析探测
├── ipc_probe.py                 # 验证 C：IPC 探测
├── smoke_e2e.py                 # 端到端冒烟测试
└── check_browser_cookies.py / test_cookiesfrombrowser.py  # Cookie 诊断记录
tests/                           # 41 个 pytest 测试
docs/                            # 设计、计划、功能清单、验证记录
build.spec                       # PyInstaller 打包配置（含瘦身）
```

## 快速开始

### 运行绿色版（推荐，无需开发环境）

1. 进入 `dist/StudyFloat_v4` 文件夹。
2. 双击 `StudyFloat_v4.exe`。
3. 首次使用点击「扫码登录」用手机 B站 App 扫码（公开视频免登录也可播放）。
4. 粘贴 Bilibili 视频链接或 BV 号，点击「播放」：
   - 课程合辑（不管链接带不带 `p`）都会弹出分P列表；链接里原有的那一P会默认高亮，选中后播放。
   - 单P视频直接播放。
5. 播放窗口默认无边框、置顶；鼠标移到画面上显示控制条，约 2 秒后自动隐藏。

> 注意：旧目录 `dist/StudyFloat`、`dist/StudyFloat_v2` 是历史版本（且被 Windows 句柄锁定无法删除），请认准 **v3**。历史目录里的 `qr_cookies.txt` 已失效，v3 需重新扫码一次。

### 开发运行

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/fetch_mpv.py
.\.venv\Scripts\python.exe -m app.main
```

### 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe tools/smoke_e2e.py   # 端到端，需要网络 + 已下载 mpv
```

### 重新打包

```powershell
.\.venv\Scripts\python.exe -m PyInstaller build.spec --noconfirm
# 输出：dist/StudyFloat_v4/（整个文件夹即绿色版，APP_NAME 在 build.spec 中修改）
```

## 登录与 Cookie

- 启动器点「扫码登录」→ 手机 B站 App 扫码确认 → 登录态保存到程序目录 `qr_cookies.txt`，之后自动使用。
- 实现基于 B站**官方 passport 扫码接口**，不读取浏览器 Cookie，因此不受 Chrome 127+ App-Bound Encryption（ABE）影响——实测 `yt-dlp --cookies-from-browser` 对 Chrome 157 的 `v20` 加密 Cookie 会报 `Failed to decrypt with DPAPI`，本项目绕开了这条不可靠路径。
- 项目只需要 `SESSDATA` 一条核心 cookie（缺失的 `buvid3` 由 yt-dlp 自动生成）；扫码会一并写入完整登录态。
- 登录态有效期约 30 天，失效后重新扫码即可；接口偶发网络失败内置 3 次重试，仍失败可能是出口 IP 被平台临时限流，请稍后再试。
- 也可在「设置」里手动指定 Netscape 格式 `cookies.txt`，优先级低于扫码登录态。
- 本项目**不绕过平台权限**：所有清晰度均以你账号本身有权访问为前提。公开视频免登录即可播放（已验证）。

## 合辑（多P）视频

B站课程通常是合辑，`p=N` 表示第 N 个分P：

- **只要是多P合辑就一定弹分P列表**，无论链接带不带 `p=N`（修复了过去带 `p` 链接被误判为「用户已指定、无需选择」而跳过列表的问题）。
- 链接里带 `p=N` 时，列表会默认高亮对应的那一P（如 `p=18` 高亮 P18），回车 / 双击 / 点「播放选中」即可。
- 列表通过官方 `view` API 一次取回全部分P（编号 / 标题 / 时长，154P 实测 0.35 秒），不逐个枚举。
- 单P视频（只有 1 个分P）直接播放，不弹列表。
- 技术要点：解析器仍**保留** `?p=N`，否则 yt-dlp 会枚举整个合辑导致解析卡死（实测 154P 不带 p 时 >75 秒无响应；带 p 时约 1.9 秒完成）。若分P接口获取失败，会回退用原链接继续播放。

## 快捷键

见 [快捷键说明](快捷键说明.md)。常用：空格播放/暂停，`←`/`→` 快退/快进 5 秒，`↑`/`↓` 音量，`[`/`]` 倍速，`m` 静音，`f` 全屏，`Esc` 退出全屏，`q` 退出。

## 依赖

- Python 3.12（仅开发 / 构建时需要）
- PySide6 ≥ 6.6、yt-dlp ≥ 2025.1.1、curl_cffi ≥ 0.11、qrcode ≥ 8.0
- pytest ≥ 8.0（测试）、pyinstaller ≥ 6.0（构建）
- mpv 随包分发，无需用户安装（由 `tools/fetch_mpv.py` 下载）

## 已知问题与限制

1. **清晰度**：免登录通常可拿到视频的最高公开清晰度（部分视频实测 1080p）；更高 / 会员清晰度需在设置中提供你自己账号的 Cookie，或扫码登录。项目不绕过平台权限。
2. **直链过期**：B站签名直链数小时后失效；每次播放都重新解析，播放中失效则关闭重开。
3. **平台风控**：可能遇到 HTTP 412 / WBI 变更；保持 yt-dlp 更新或提供真实 Cookie，错误会显示简洁中文提示。
4. **杀毒误报**：PyInstaller 与 mpv.exe 未签名，可能被误报；加白名单即可。
5. **绿色版体积**：约 217MB，其中 mpv.exe 独占约 117MB（静态编译、内置 FFmpeg 与全编解码器，是“真播放”的必要成本），其余为 Python 运行时 + Qt Widgets + yt-dlp。已从初版 810MB 精简掉未使用的 Qt WebEngine / Qml / Quick 模块。
6. **IPC 死锁历史**：Windows 命名管道 + 后台读线程 + 管道关闭曾导致 `command()` 卡死；现改为同步「写一帧、读到匹配 request_id」并 `quit` 后再关管道，stdout/stderr 置 `DEVNULL`，已稳定。
7. **无自定义右键菜单 / 系统托盘**：P0 用快捷键 + 设置窗口提供等价操作，播放后启动器最小化；完整右键菜单与托盘常驻属于 P1。
8. **无自定义快捷键配置 UI**：当前绑定写在 `input.conf`，可视化配置属于 P1。

## 功能清单 / 未完成

完整清单见 [功能清单](docs/功能清单.md)。P1（托盘、右键菜单、清晰度切换、历史、快捷键配置、多窗口等）与 P2（浏览器插件、YouTube、播放列表、字幕、主题等）均**未实现**，不在本轮范围。
