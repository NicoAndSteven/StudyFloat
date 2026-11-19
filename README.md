# StudyFloat

极简独立视频悬浮播放器 —— 把 Bilibili 视频从浏览器中提取出来，在 Windows 桌面上以一个独立、无边框、可置顶、可自由缩放的窗口播放。

## 项目状态

**P0（MVP）已完成。** 技术验证 A/B/C 全部通过，27 个自动化测试通过，端到端播放链路实测通过，Windows 免安装绿色版已构建。

## 技术选型及理由

| 组件 | 选型 | 理由 |
|---|---|---|
| 启动器 UI | Python 3.12 + PySide6 | 极简界面足够；打包成熟；LGPL 许可 |
| 视频解析 | yt-dlp（库模式） | 支持 B站 DASH 直链、WBI 签名、可选 Cookie |
| 播放引擎 | 独立 `mpv.exe` 进程 | 真正独立窗口；浏览器/启动器关闭后仍播放；硬解低占用；JSON IPC 精确控制 |
| IPC | Windows 命名管道 + 换行 JSON | 同步请求/响应，避免线程竞争（见已知问题） |
| 控制层 | mpv 内建 OSC（Lua script-opts） | 与视频窗口一体，悬停显示、静止隐藏，无额外窗口 |
| 打包 | PyInstaller `--onedir` | 免安装绿色文件夹，无需 Python 环境 |

完整设计见 [设计规格](docs/superpowers/specs/2026-11-19-studyfloat-design.md)，验证记录见 [验证记录](docs/验证记录.md)。

## 目录结构

```
app/
├── main.py                    # 入口：输入 → 解析 → 启动 mpv
├── config.py                  # 设置持久化（JSON）
├── source/
│   ├── url_validator.py       # BV 链接校验与规范化
│   └── bilibili_parser.py     # yt-dlp 解析 → StreamInfo（解析与播放解耦）
├── player/
│   ├── mpv_controller.py      # mpv 子进程 + 命名管道 IPC
│   ├── errors.py              # 用户可见的异常类型
│   └── resources/
│       ├── studyfloat.lua     # 极简 OSC 配置
│       └── input.conf         # 快捷键绑定
├── ui/
│   ├── launcher.py            # URL 输入窗口
│   └── settings_dialog.py     # 设置窗口
└── window/geometry.py         # 窗口几何预设与记忆
tools/
├── fetch_mpv.py               # 下载便携版 mpv
├── parse_probe.py             # 验证 A 脚本
├── ipc_probe.py               # 验证 C 脚本
└── smoke_e2e.py               # 端到端冒烟脚本
tests/                         # 27 个 pytest 测试
docs/                          # 设计、计划、验证记录
```

## 扫码登录（免复制粘贴）

启动器点击「扫码登录」，用手机 B站 App 扫描二维码并确认，登录态会自动保存到程序目录的 `qr_cookies.txt`，之后播放时自动使用，**无需手动导出或粘贴任何 Cookie**。

- 原理：调用 B站官方 passport 扫码接口（不读取浏览器 Cookie，因此不受 Chrome 127+ App-Bound Encryption 影响）。
- yt-dlp 实际只需要 `SESSDATA` 一条核心 cookie（缺失的 `buvid3` 它会自动生成）；扫码会一并拿到 `bili_jct`/`DedeUserID` 等完整登录态。
- 登录态有效期约 30 天，失效后重新扫码即可。
- 若扫码接口偶发网络失败，模块内置 3 次重试；如仍失败请稍后再试（可能是出口 IP 被平台临时限流）。
- 想手动提供 Cookie 也可以：在「设置」里指定 Netscape 格式 `cookies.txt`，优先级低于扫码登录态。

> 说明：B站免登录也能播放公开视频（已验证），扫码登录主要用于解锁更高清晰度与规避 412 风控。项目不绕过平台权限，登录完全基于你自己的账号。

## 快速开始

### 运行（无需开发环境）

1. 进入 `dist/StudyFloat` 文件夹。
2. 双击 `StudyFloat.exe`。
3. 粘贴 Bilibili 视频链接或 BV 号，点击「播放」。

### 开发运行

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/fetch_mpv.py
.\.venv\Scripts\python.exe -m app.main
```

### 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
.\.venv\Scripts\python.exe tools/smoke_e2e.py   # 需要网络 + 已下载 mpv
```

### 重新打包

```powershell
.\.venv\Scripts\python.exe -m PyInstaller build.spec --noconfirm
# 输出：dist/StudyFloat/（整个文件夹即为绿色版）
```

## 依赖

- Python 3.12（仅开发/构建时需要）
- PySide6 ≥ 6.6
- yt-dlp ≥ 2025.1.1
- pyinstaller ≥ 6.0（构建时）
- pytest ≥ 8.0（测试时）
- mpv（随包分发，无需用户安装；`tools/fetch_mpv.py` 下载）

## 已知问题与限制

1. **清晰度**：免登录通常可拿到所访问视频的最高公开清晰度（实测部分视频可达 1080p）；更高/会员清晰度需用户在设置中提供自己的 Cookie（Netscape `cookies.txt`）。项目不绕过平台权限。
2. **直链过期**：B站签名直链数小时后失效；每次播放都会重新解析。播放中若失效，关闭重开即可。
3. **平台反爬**：可能遇到 HTTP 412 / WBI 变更；保持 yt-dlp 更新，或提供真实 Cookie。错误会显示简洁中文提示。
4. **杀毒误报**：PyInstaller 与 mpv.exe 未签名，可能被误报；将文件夹加入白名单即可。
5. **绿色版体积**：约 208MB，其中 mpv.exe 独占约 117MB（静态编译、内置 FFmpeg 与全编解码器，是“真播放”的必要成本），其余为 Python 运行时 + Qt Widgets + yt-dlp。已从初版的 810MB 精简掉未使用的 Qt WebEngine/Qml/Quick 模块。
6. **无自定义右键菜单**：P0 用快捷键 + 设置窗口提供等价操作；完整右键菜单属于 P1。
7. **系统托盘**：P0 播放后启动器最小化；托盘常驻属于 P1。

## 功能清单 / 未完成

见 [功能清单](docs/功能清单.md)。

## 快捷键

见 [快捷键说明](快捷键说明.md)。
