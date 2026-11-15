#!/usr/bin/env python3
"""Optional local faster-whisper transcription, no cloud media upload."""
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model", default="small", help="已有本地模型目录，或确认下载的模型名称")
    p.add_argument("--allow-download", action="store_true", help="允许下载缺失模型；媒体仍在本机处理")
    a = p.parse_args()
    if not a.video.is_file():
        p.error("视频文件不存在")
    if a.output.exists() or a.output.resolve() == a.video.resolve():
        p.error("输出已存在或与原片相同，请使用新文件名")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        p.error("缺少 faster-whisper，请按 references/setup.md 安装独立转写环境")
    model = WhisperModel(a.model, device="cpu", compute_type="int8",
                         local_files_only=not a.allow_download)
    segments, info = model.transcribe(str(a.video.resolve()), language="zh",
                                      word_timestamps=True, vad_filter=False)
    data = {"language": info.language, "segments": []}
    for s in segments:
        data["segments"].append({"id": s.id, "start": s.start, "end": s.end, "text": s.text,
                                 "words": [{"start": w.start, "end": w.end, "word": w.word}
                                           for w in (s.words or [])]})
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(a.output)


if __name__ == "__main__":
    main()
