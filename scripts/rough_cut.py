#!/usr/bin/env python3
"""Local, review-first rough cuts. Semantic decisions belong to the agent/user."""
import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path


def run(args):
    result = subprocess.run(args, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(f"{Path(args[0]).name} 执行失败：{result.stderr.strip()}")
    return result.stdout


def probe(path):
    data = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                           "-of", "json", str(path)]))
    video = next((s for s in data["streams"] if s["codec_type"] == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        raise ValueError("输入必须包含视频轨道")
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    duration = float(video.get("duration") or data["format"]["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("无法确定视频时长")
    return {"duration": duration, "video": video, "audio": audio}


def validate_plan(plan, duration):
    rows = plan.get("keep")
    if not isinstance(rows, list) or not rows:
        raise ValueError("keep 必须是非空片段列表")
    if plan.get("needs_review"):
        raise ValueError("needs_review 尚有未确认片段，请先完成取舍")
    previous = 0.0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"片段 {i + 1} 必须是对象")
        a, b = row.get("start"), row.get("end")
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) for v in (a, b)):
            raise ValueError(f"片段 {i + 1} 时间必须是有限数字（秒）")
        if a < previous or not 0 <= a < b <= duration:
            raise ValueError(f"片段 {i + 1} 越界、重叠或顺序错误")
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise ValueError(f"片段 {i + 1} 缺少保留理由")
        previous = b
    return rows


def report(rows, duration, digest):
    kept = sum(r["end"] - r["start"] for r in rows)
    lines = ["# 口播粗剪清单", "", f"清单 SHA256：`{digest}`", "",
             f"原片 {duration:.3f} 秒；预计保留 {kept:.3f} 秒；删除 {duration-kept:.3f} 秒。",
             "", "| 原片起止（秒） | 输出起止（秒） | 保留理由 |",
             "| --- | --- | --- |"]
    offset, cursor, removed = 0.0, 0.0, []
    for row in rows:
        a, b = row["start"], row["end"]
        if a > cursor:
            removed.append([cursor, a])
        reason = row["reason"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {a:.3f}–{b:.3f} | {offset:.3f}–{offset+b-a:.3f} | {reason} |")
        offset += b-a
        cursor = b
    if cursor < duration:
        removed.append([cursor, duration])
    lines += ["", "删除区间（需要结合逐字稿解释删除理由）：", "",
              *[f"- {a:.3f}–{b:.3f} 秒" for a, b in removed], "",
              "请审核重说取舍及全部删除区间；本脚本不判断句意，也不自动批准剪辑。"]
    return "\n".join(lines), kept


def check_media(info):
    v = info["video"]
    if v.get("color_transfer") in ("smpte2084", "arib-std-b67"):
        raise ValueError("v1 仅支持 SDR；HDR 需要另行确认色彩转换方案")
    rotations = [s.get("rotation", 0) for s in v.get("side_data_list", [])]
    rotations.append(v.get("tags", {}).get("rotate", 0))
    if any(float(r) % 360 for r in rotations):
        raise ValueError("素材含旋转元数据，请先生成方向已烘焙的工作副本，不改原片")
    if v["width"] % 2 or v["height"] % 2:
        raise ValueError("v1 的 H.264 输出需要偶数宽高；不自动裁切原片")
    fps = Fraction(v.get("avg_frame_rate", "0/1"))
    nominal = Fraction(v.get("r_frame_rate", "0/1"))
    if fps <= 0 or nominal <= 0 or abs(float(fps / nominal)-1) > 0.001:
        raise ValueError("v1 需要恒定帧率素材；请先确认变帧率工作副本的转换方案")
    return str(fps)


def render(source, info, rows, output, expected):
    fps = check_media(info)
    if output.suffix.lower() != ".mp4":
        raise ValueError("输出扩展名必须是 .mp4")
    if output.exists() or output.resolve() == source.resolve():
        raise ValueError("输出已存在或与原片相同，请选择新文件名")
    output.parent.mkdir(parents=True, exist_ok=True)
    filters, labels = [], []
    for i, row in enumerate(rows):
        a, b = row["start"], row["end"]
        filters.append(f"[0:{info['video']['index']}]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]")
        labels.append(f"[v{i}]")
        if info["audio"]:
            filters.append(f"[0:{info['audio']['index']}]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]")
            labels.append(f"[a{i}]")
    has_audio = bool(info["audio"])
    filters.append("".join(labels) + f"concat=n={len(rows)}:v=1:a={int(has_audio)}[v]"
                   + ("[a]" if has_audio else ""))
    # A filter file avoids shell interpretation and OS command-length limits.
    with tempfile.TemporaryDirectory(prefix="rough-cut-") as temp:
        graph = Path(temp) / "filter.txt"
        graph.write_text(";\n".join(filters), encoding="utf-8")
        # FFmpeg 9 removed the legacy option; older builds still need it.
        options = run(["ffmpeg", "-hide_banner", "-h", "full"])
        filter_option = "-filter_complex_script" if "-filter_complex_script" in options else "-/filter_complex"
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
               "-i", str(source), filter_option, str(graph), "-map", "[v]"]
        if has_audio:
            cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
        cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt",
                "yuv420p", "-r", fps, "-map_metadata", "-1", "-movflags", "+faststart",
                str(output)]
        run(cmd)
    actual = probe(output)
    # Each edit boundary is quantized to frames; AAC adds a small encoder delay.
    tolerance = max(0.15, len(rows) * 2 / float(Fraction(fps)))
    if abs(actual["duration"] - expected) > tolerance:
        raise ValueError("输出时长未通过校验，请检查输出，勿作为已完成结果交付")
    if (actual["video"]["width"], actual["video"]["height"]) != (info["video"]["width"], info["video"]["height"]):
        raise ValueError("输出画幅未通过校验")
    run(["ffmpeg", "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"])
    return {"output": str(output), "expected_seconds": round(expected, 3),
            "actual_seconds": actual["duration"], "segments": len(rows),
            "next": "人工抽听所有接缝，确认无截字、误删与不自然停顿"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    for name in ("plan", "render"):
        p = sub.add_parser(name)
        p.add_argument("--video", type=Path, required=True)
        p.add_argument("--plan", type=Path, required=True)
        if name == "render":
            p.add_argument("--output", type=Path, required=True)
            p.add_argument("--approved-sha256", required=True,
                           help="审核通过的 plan 命令所显示的清单哈希")
    args = parser.parse_args()
    if args.command == "doctor":
        tools = {x: shutil.which(x) for x in ("ffmpeg", "ffprobe")}
        print(json.dumps({"python": sys.version.split()[0], "tools": tools,
                          "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
                          "note": "转写可使用已有带时间码逐字稿；渲染需要 FFmpeg 的 libx264/AAC"}, ensure_ascii=False, indent=2))
        return 0 if all(tools.values()) else 1
    source = args.video.resolve(strict=True)
    payload = args.plan.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    info = probe(source)
    rows = validate_plan(json.loads(payload.decode("utf-8")), info["duration"])
    summary, expected = report(rows, info["duration"], digest)
    if args.command == "plan":
        print(summary)
    else:
        if args.approved_sha256 != digest:
            raise ValueError("清单已变更或哈希不匹配，请重新审核")
        print(json.dumps(render(source, info, rows, args.output.resolve(), expected), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(f"错误：{detail}", file=sys.stderr)
        sys.exit(1)
