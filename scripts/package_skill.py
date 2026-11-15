#!/usr/bin/env python3
"""Build generic and WorkBuddy ZIPs from the same source, with an allowlist."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = 'qiqi-spoken-rough-cut'
VERSION = '1.0.0'
FILES = ['SKILL.md', 'README.md', 'LICENSE', 'scripts/rough_cut.py', 'scripts/transcribe.py',
         'references/decisions.md', 'references/plan.md', 'references/setup.md', 'examples/plan.json']
DISPLAY = {
    'display_name': '奇奇口播粗剪',
    'display_name_en': 'Qiqi Spoken Rough Cut',
    'description_zh': '整理中文单人口播中的重说、口误和半句，保留完整表达。先审核剪切清单，再本地导出初剪视频。需要 Python 与 FFmpeg，可使用已有逐字稿或本地转写。',
    'description_en': 'Review Chinese talking-head retakes and false starts, approve a cut list, then render locally. Requires Python and FFmpeg; accepts timestamped transcripts or optional local transcription.',
    'version': VERSION,
    'author': 'qiqi-huang-ai',
    'examples_zh': ['粗剪这段中文口播，删重说，保留最后一遍完整表达，先给我审核清单。', '这段口播最后一遍没说完，请保留前一遍完整表达。', '使用现有带时间码逐字稿，只做纯粗剪，保留有意强调和自然停顿。'],
    'examples_en': ['Rough-cut this Chinese talking-head video. Show the cut list before rendering.', 'Keep the previous complete take when the final retake is unfinished.', 'Use my timestamped transcript for a plain rough cut; preserve intentional emphasis and natural pauses.']
}


def main():
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    sums = []
    for platform in ('generic', 'workbuddy'):
        target = dist / f'{NAME}-{platform}-{VERSION}.zip'
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
            for filename in FILES:
                data = (ROOT / filename).read_bytes()
                if platform == 'workbuddy' and filename == 'SKILL.md':
                    text = data.decode('utf-8')
                    end = text.index('\n---', 3)
                    # JSON scalar/list syntax is valid YAML; preserve shared metadata/body.
                    fields = ''.join('\n'+k+': '+json.dumps(v, ensure_ascii=False) for k,v in DISPLAY.items())
                    data = (text[:end] + fields + text[end:]).encode('utf-8')
                item = zipfile.ZipInfo(f'{NAME}/{filename}', date_time=(2026, 11, 16, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                item.external_attr = 0o644 << 16
                z.writestr(item, data)
        sums.append(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name)
        print(target)
    (dist / 'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n')


if __name__ == '__main__':
    main()
