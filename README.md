# 奇奇口播粗剪 · Qiqi Spoken Rough Cut

一个面向中文单人口播的 Agent Skill：识别重说、口误、没说完的半句和重录空档，先给你看剪切清单，确认后再输出初剪视频。

**保留最后一次完整表达；最后一遍没说完，就回到上一遍。**

适合知识口播、产品讲解、课程录制的第一遍整理。原片保持不变，不加字幕、音乐或缩放，不把观点改写成摘要。语义取舍由使用 Skill 的 AI Agent 判断；本地脚本负责校验和渲染，不能单凭静音或文字相似度自动决定删什么。

## 安装

通过支持 Agent Skills 的安装器：

```bash
npx skills add qiqi-huang-ai/qiqi-spoken-rough-cut
```

按安装器提示选择可用宿主。也可下载 Release 中的通用技能包，解压到宿主的 Skills 目录。WorkBuddy 本地上传请使用 `qiqi-spoken-rough-cut-workbuddy-1.0.0.zip`；它包含 WorkBuddy 展示字段，与通用包使用相同正文和脚本。市场公开上架需另经平台审核，本地导入不代表已上架。

## 这样使用

```text
帮我粗剪这个中文口播：/完整路径/原片.mp4。
删掉重说、口误和没说完的半句，保留最后一次完整表达。
先给我看剪切清单，确认后再输出视频。
```

如果有逐字稿，可一起提供：

```text
原片是 /完整路径/原片.mp4，带时间码逐字稿是 /完整路径/transcript.json。
只做纯粗剪，保留有意强调和自然停顿。
```

完成后交付：初剪 MP4、剪切清单、原片与成片时长、每处取舍说明。需要换一遍口播时，修改清单后用新文件名重新导出。

## 判断示例

| 原片里发生了什么 | 如何处理 |
| --- | --- |
| 同一句说三遍，第三遍完整 | 保留第三遍 |
| 第一遍完整，最后一遍放弃 | 保留第一遍 |
| “先做出来，先做出来，再优化” | 保留有意强调 |
| 两句开头相同，但补充的信息不同 | 两句都保留 |
| 数字说错后又没说完整 | 列为待确认，不替用户猜 |

更多例子见 [中文取舍规则](references/decisions.md)。

## 环境与运行

需要 Python 3.10+、FFmpeg/FFprobe（libx264/AAC），以及能访问本地文件并执行命令的 AI 宿主。渲染脚本只使用 Python 标准库。已有带时间码逐字稿时，无需额外语音模型；可选本地转写使用 faster-whisper，需独立安装与下载模型。详见 [安装与转写](references/setup.md)。

```bash
python3 scripts/rough_cut.py doctor
python3 scripts/rough_cut.py plan --video /路径/原片.mp4 --plan /路径/plan.json
```

审核清单后，用 plan 输出的 SHA256：

```bash
python3 scripts/rough_cut.py render --video /路径/原片.mp4 --plan /路径/plan.json --output /路径/初剪.mp4 --approved-sha256 审核清单的哈希
```

Windows 可将 `python3` 替换为 `python`。路径含空格需加引号。

[plan.json 示例](examples/plan.json) 使用的是合成测试时间，不能直接用于你的原片。未包含在 keep 里的时间会被删除，详见 [清单格式](references/plan.md)。

## v1 边界与验证

- 单个 SDR、恒定帧率、方向已烘焙、偶数宽高视频；使用第一条视频和音频轨，输出 H.264/AAC MP4。重新编码不等于无损剪辑。
- 不自动处理 HDR、旋转元数据、多机位或剪映草稿，不提供社交平台发布。
- 渲染前拦截越界、重叠、乱序、未决事项与清单哈希不符；不覆盖原片或已有输出。
- 渲染后核对时长、画幅并完整解码；仍需核听接缝和复核语义。
- 已在 macOS 通过合成音视频测试：保留区间的实际画面、时长、帧率、音轨同步、无音轨视频、原片不变、输出不覆盖及错误清单拦截。
- CI 运行 Linux/macOS/Windows 渲染测试。请以仓库 Actions 最新结果为准；这不代表所有宿主已通过完整兼容验证。
- 可选 faster-whisper 转写入口与人工语义规则不由合成渲染测试证明；识别准确率和剪辑质量需要用你的真实口播复核。

```bash
python3 -m unittest discover -s tests -v
```

## 隐私与许可

默认不上传媒体，不记录遥测，不读取任何账号凭证。只打包代码、说明和合成文本示例，不包含作者或客户视频。可选模型下载访问模型托管服务，但不会上传你的原片。

本仓库代码与示例采用 [MIT](LICENSE)。FFmpeg、语音模型和转写依赖未打包，其许可由各自项目提供。问题与反馈请提交 [Issue](https://github.com/qiqi-huang-ai/qiqi-spoken-rough-cut/issues)。
