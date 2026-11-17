"""선정한 평가용 사진을 data/photos/ 에 .jpg 복사본으로 만들고, 확인 도구용 목록(tool/photos.js)을 생성한다.

원본은 수정하지 않는다. 원본 확장자가 .DNG여도 실제로는 JPEG라서 Pillow로 그대로 읽는다.

사용법 (프로젝트 루트에서):
    python scripts/prepare_photos.py "<원본 사진 폴더>"
"""
import csv
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

MAX_SIDE = 3000  # 긴 변 기준 (원본 8064px은 세기에 과하게 크다)

root = Path(__file__).resolve().parent.parent
if len(sys.argv) != 2:
    sys.exit('usage: python scripts/prepare_photos.py "<source photo folder>"')
src_dir = Path(sys.argv[1])

out_dir = root / "data" / "photos"
out_dir.mkdir(parents=True, exist_ok=True)

photos = []
with open(root / "data" / "selection.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        name = row["file"]
        candidates = [p for p in src_dir.glob(f"{name}.*") if p.is_file()]
        if not candidates:
            sys.exit(f"source not found: {name}")
        im = ImageOps.exif_transpose(Image.open(candidates[0])).convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        dst = out_dir / f"{name}.jpg"
        im.save(dst, quality=90)
        photos.append(
            {
                "file": name,
                "scene": row["scene"],
                "difficulty": row["difficulty"],
                "src": f"../data/photos/{name}.jpg",
            }
        )
        print(f"{name}: {im.size[0]}x{im.size[1]}")

# 선정에서 빠진 이전 복사본 정리
keep = {f"{x['file']}.jpg" for x in photos}
for old in out_dir.glob("*.jpg"):
    if old.name not in keep:
        old.unlink()
        print("removed stale", old.name)

tool_dir = root / "tool"
tool_dir.mkdir(exist_ok=True)
(tool_dir / "photos.js").write_text(
    "window.PHOTOS = " + json.dumps(photos, ensure_ascii=False, indent=1) + ";\n",
    encoding="utf-8",
)
print(f"done: {len(photos)} photos")
