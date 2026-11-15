# 安装与本地转写

## 最小依赖

- 能读写本地文件、执行命令的 Skill 宿主（如 WorkBuddy、Codex）。
- Python 3.10+。
- PATH 中有 ffmpeg、ffprobe；FFmpeg 包含 libx264 与 AAC 编码器。

运行 `python3 scripts/rough_cut.py doctor` 查看依赖。macOS 常用 `brew install ffmpeg`；Windows 可使用 `winget install Gyan.FFmpeg`；Ubuntu 常用 `sudo apt install ffmpeg`。安装依赖前说明实际命令，由用户决定；本 Skill 不自动执行安装。

剪辑脚本仅使用 Python 标准库。已有带时间码的逐字稿时，不必安装任何语音模型。

## 可选的 faster-whisper 转写

在用户自己的工作目录创建独立环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install faster-whisper
.venv/bin/python /完整路径/qiqi-spoken-rough-cut/scripts/transcribe.py /视频路径/原片.mp4 --output /新工作目录/transcript.json --model /已下载模型目录
```

Windows 将 `.venv/bin/python` 换成 `.venv\Scripts\python.exe`。下载模型需要网络、空间和等待时间；默认不下载。用户同意后可使用 `--model small --allow-download`。模型由 faster-whisper 下载，实际大小随选择的模型而变化；中文准确率与硬件速度也不同。

音视频只在本机处理；模型下载会连接模型托管服务，但不上传媒体。转写可能遗漏语气词、口误或重复，必须结合原音频审核。输出 JSON 包含片段及词级时间戳，供 Agent 制定清单。

如果宿主已有本地转写方式，可以直接使用，不强制绑定某个模型。云端转写不属于默认流程，必须先取得用户对上传媒体的明确同意。

## 版本边界

不要把作者机器的路径写进配置。工作文件、原片、转写和结果均放在用户选择的工作目录，不写入 Skill 安装目录。Python/FFmpeg 的跨平台命令在 CI 中检测；发布说明会单独注明实际通过的运行验证，不能将此视为所有宿主的完整兼容认证。
