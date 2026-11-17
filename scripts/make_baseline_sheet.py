"""현행 방식 기준선 측정용 종이 기록지(PDF)를 만든다. data/selection.csv의 평가셋(쉬움 제외)을 쓴다.

사용법 (프로젝트 루트에서):
    python scripts/make_baseline_sheet.py
"""
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent.parent
FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_B = "C:/Windows/Fonts/malgunbd.ttf"
W, H = 3508, 2480  # A4 가로, 300dpi
M = 140

rows = [r for r in csv.DictReader(open(root / "data" / "selection.csv", encoding="utf-8")) if r["difficulty"] != "easy"]
kor = {"medium": "보통", "hard": "어려움"}

f = lambda s, b=False: ImageFont.truetype(FONT_B if b else FONT, s)
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)

d.text((M, 100), "현행 방식 기준선 기록지", font=f(72, True), fill="black")
d.text((M, 200), "눈으로 세기 → 종이에 적기.  8종만 센다(기타는 세지 않음).  확대하지 않고 한 화면에서 본다.  몸통이 절반 이상 보이면 센다.", font=f(38), fill="#333")
d.text((M, 262), "사진을 여는 순간 스톱워치 시작 → 마지막 숫자를 적는 순간 정지 → 초 칸에 적고 0으로 돌린다.  틀린 것 같아도 다시 세지 않는다.", font=f(38), fill="#333")

cols = [("순서", 110), ("사진", 250), ("난이도", 190), ("초", 190),
        ("참이슬\n(P1)", 230), ("처음처럼\n(P2)", 230), ("카스\n500(P3)", 230), ("테라\n500(P4)", 230),
        ("콜라\n355(P5)", 230), ("제로\n250(P6)", 230), ("사이다\n250(P7)", 230), ("콜라페트\n500(P8)", 260)]
total = sum(w for _, w in cols)
scale = (W - 2 * M) / total
cols = [(n, int(w * scale)) for n, w in cols]

top = 380
head_h = 150
row_h = 122
x = M
d.rectangle([M, top, M + sum(w for _, w in cols), top + head_h], fill="#eef1f5", outline="black", width=3)
for name, w in cols:
    lines = name.split("\n")
    y = top + head_h // 2 - len(lines) * 24
    for ln in lines:
        tw = d.textlength(ln, font=f(40, True))
        d.text((x + (w - tw) / 2, y), ln, font=f(40, True), fill="black")
        y += 52
    x += w

for i, r in enumerate(rows):
    y0 = top + head_h + i * row_h
    d.rectangle([M, y0, M + sum(w for _, w in cols), y0 + row_h], outline="black", width=2)
    cells = [str(i + 1), r["file"].replace("IMG_", ""), kor[r["difficulty"]]]
    x = M
    for ci, (name, w) in enumerate(cols):
        if ci < 3:
            tw = d.textlength(cells[ci], font=f(46, ci == 1))
            d.text((x + (w - tw) / 2, y0 + 32), cells[ci], font=f(46, ci == 1), fill="black")
        d.line([x, y0, x, y0 + row_h], fill="black", width=2)
        x += w
    d.line([x, y0, x, y0 + row_h], fill="black", width=2)

yb = top + head_h + len(rows) * row_h + 60
d.text((M, yb), "합계 (세고 적는 시간 합):  __________ 초", font=f(48, True), fill="black")
d.text((M, yb + 90), "시트(data/baseline_manual.csv)에 12장을 옮겨 적는 시간:  __________ 초   (data/baseline_manual_total.csv에 기록)", font=f(48, True), fill="black")
d.text((M, H - 110), "시작 시각: __________    끝난 시각: __________    메모: ______________________________________________", font=f(38), fill="#333")

out = root / "data" / "baseline_paper_sheet.pdf"
img.save(out, "PDF", resolution=300)
print("saved", out.name)
