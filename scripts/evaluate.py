"""예측 개수 CSV를 정답과 비교해 문제정의서의 성공 기준(S1~S5)을 계산한다.

예측 파일 형식 (둘 중 하나)
  긴 형식:  file,product,count          (product는 P1~P8 또는 other, 없는 제품은 행이 없으면 0)
  넓은 형식: file,P1,P2,...,P8[,other]   (예: data/baseline_manual.csv)

사용법 (프로젝트 루트에서)
  python scripts/evaluate.py results/A/pred.csv --seconds 150.0
  python scripts/evaluate.py data/baseline_manual.csv --no-other        # 사람 기준선 채점
  python scripts/evaluate.py pred.csv --out results/A/metrics.json

채점 규칙(문제정의서 6장)
  S1  사진별 전체 용기 수 오차 <= max(1, 정답*10%)인 사진 수
  S2  사진x제품 칸의 오차 <= 1 비율 (정답 또는 예측이 0보다 큰 칸만, P4·P6·경계 칸은 제외하고 따로 보고)
  S3  --seconds(AI 총 시간, 평가셋 12장)가 기준선 대비 50% 이상 줄었는지
  S4  같은 칸에서 제품별 발주량이 정답 개수로 계산한 발주량과 같은 비율
  S5  8종 예측 합계가 정답 합계를 넘은 양의 합(기타를 8종으로 센 것의 대략치, 정확한 값은 박스 단위 결과가 필요)
세트: 평가셋(보통+어려움)이 성공 판정, 개발셋(쉬움)·전체 20장은 참고.
"""
import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

try:  # Colab·Jupyter의 출력 객체에는 reconfigure가 없을 수 있다
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = [f"P{i}" for i in range(1, 9)]
PAR = {"P1": 20, "P2": 20, "P3": 12, "P4": 12, "P5": 12, "P6": 12, "P7": 12, "P8": 12}
UNIT = {"P1": 10, "P2": 10, "P3": 6, "P4": 6, "P5": 6, "P6": 6, "P7": 6, "P8": 6}
SMALL = {"P4", "P6"}                    # 정답 개수가 너무 적어 제품별 결론에서 제외
BOUNDARY = {("IMG_4193", "P8")}         # 반쯤 잘린 용기(사람 판단 경계)라 채점에서 제외


def order_qty(product, n):
    short = PAR[product] - n
    return 0 if short <= 0 else math.ceil(short / UNIT[product]) * UNIT[product]


def read_long_or_wide(path):
    """file -> {product: count} 로 읽는다."""
    out = defaultdict(lambda: defaultdict(int))
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        cols = [c.strip() for c in (rd.fieldnames or [])]
        if "file" not in cols:
            sys.exit(f"'file' 열이 없습니다: {path}")
        if "product" in cols:
            cc = next((c for c in ("count", "visible_count", "n") if c in cols), None)
            if cc is None:
                sys.exit("긴 형식에는 count(또는 visible_count) 열이 필요합니다")
            for r in rd:
                out[r["file"]][r["product"]] += int(float(r[cc]))
        elif "P1" in cols:
            for r in rd:
                for p in PRODUCTS + ["other"]:
                    if p in r and r[p] not in ("", None):
                        out[r["file"]][p] += int(float(r[p]))
                out[r["file"]]  # 값이 모두 0이어도 사진은 존재하는 것으로 둔다
        else:
            sys.exit("긴 형식(file,product,count) 또는 넓은 형식(file,P1..P8) 이어야 합니다")
    return out


def load_selection():
    sets = {"eval": [], "dev": []}
    with open(ROOT / "data" / "selection.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sets["dev" if r["difficulty"] == "easy" else "eval"].append(r["file"])
    sets["all"] = sets["dev"] + sets["eval"]
    return sets


def score(files, gt, pred, include_other):
    prods = PRODUCTS + (["other"] if include_other else [])
    res = {"n_photos": len(files)}

    # S1 총 개수
    ok1, detail1 = 0, []
    for fn in files:
        g = sum(gt[fn].get(p, 0) for p in prods)
        q = sum(pred[fn].get(p, 0) for p in prods)
        tol = max(1.0, 0.1 * g)
        ok = abs(q - g) <= tol
        ok1 += ok
        detail1.append({"file": fn, "gt": g, "pred": q, "tol": round(tol, 2), "ok": ok})
    res["S1"] = {"ok": ok1, "of": len(files), "photos": detail1}

    # S2, S4 제품 칸
    main, small, boundary = [], [], []
    for fn in files:
        for p in PRODUCTS:
            g, q = gt[fn].get(p, 0), pred[fn].get(p, 0)
            if g == 0 and q == 0:
                continue
            cell = {"file": fn, "product": p, "gt": g, "pred": q,
                    "ok_count": abs(q - g) <= 1,
                    "ok_order": order_qty(p, q) == order_qty(p, g)}
            if (fn, p) in BOUNDARY:
                boundary.append(cell)
            elif p in SMALL:
                small.append(cell)
            else:
                main.append(cell)
    n = len(main)
    res["S2"] = {"ok": sum(c["ok_count"] for c in main), "of": n,
                 "rate": round(sum(c["ok_count"] for c in main) / n, 3) if n else None}
    res["S4"] = {"ok": sum(c["ok_order"] for c in main), "of": n,
                 "rate": round(sum(c["ok_order"] for c in main) / n, 3) if n else None}
    res["wrong_cells"] = [c for c in main if not c["ok_count"]]
    res["small_cells(P4,P6)"] = small
    res["boundary_cells"] = boundary

    # S5 8종 과다 집계(대략치)
    over = 0
    for fn in files:
        g8 = sum(gt[fn].get(p, 0) for p in PRODUCTS)
        q8 = sum(pred[fn].get(p, 0) for p in PRODUCTS)
        over += max(0, q8 - g8)
    res["S5_over_count_proxy"] = over

    # 참고: 제품별 평균 절대오차 (모든 칸 포함)
    mae = {}
    for p in PRODUCTS:
        errs = [abs(pred[fn].get(p, 0) - gt[fn].get(p, 0)) for fn in files]
        mae[p] = round(sum(errs) / len(errs), 2) if errs else None
    res["MAE_by_product"] = mae
    return res


def baseline_seconds():
    p1 = ROOT / "data" / "baseline_manual.csv"
    p2 = ROOT / "data" / "baseline_manual_total.csv"
    if not (p1.exists() and p2.exists()):
        return None
    with open(p1, encoding="utf-8-sig") as f:
        a = sum(float(r["seconds_count_write"]) for r in csv.DictReader(f) if r["seconds_count_write"])
    with open(p2, encoding="utf-8-sig") as f:
        b = sum(float(r["seconds"]) for r in csv.DictReader(f) if r["seconds"])
    return a, b


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pred", help="예측 개수 CSV")
    ap.add_argument("--truth", default=str(ROOT / "data" / "ground_truth.csv"))
    ap.add_argument("--no-other", action="store_true", help="기타를 제외한 8종 합계로 S1을 계산(사람 기준선 같은 경우)")
    ap.add_argument("--seconds", type=float, help="AI 쪽 총 시간(초): 평가셋 12장, 처리 + 사람 확인·수정")
    ap.add_argument("--out", help="결과 JSON 저장 경로")
    a = ap.parse_args()

    gt = read_long_or_wide(a.truth)
    pred = read_long_or_wide(a.pred)
    sets = load_selection()

    missing = [f for f in sets["all"] if f not in pred]
    extra = [f for f in pred if f not in sets["all"]]
    if missing:
        print(f"[경고] 예측에 없는 사진은 0개로 계산합니다: {missing}")
    if extra:
        print(f"[경고] 평가 대상이 아닌 사진은 무시합니다: {extra}")

    # 개발셋 사진이 예측에 전혀 없으면(예: 평가셋 12장만 채점한 기준선) 참고용 세트는 건너뛴다
    only_eval = all(f in missing for f in sets["dev"])
    if only_eval:
        print("[안내] 개발셋 예측이 없어 평가셋만 채점합니다.")

    results = {}
    for name, label in (("eval", "평가셋 (성공 판정)"), ("dev", "개발셋 (참고)"), ("all", "전체 20장 (참고)")):
        if only_eval and name != "eval":
            continue
        results[name] = score(sets[name], gt, pred, include_other=not a.no_other)
        r = results[name]
        print(f"\n## {label} — {r['n_photos']}장")
        print(f"- S1 총 개수: {r['S1']['ok']}/{r['S1']['of']}장")
        s2, s4 = r["S2"], r["S4"]
        print(f"- S2 제품별(±1): {s2['ok']}/{s2['of']}칸 ({s2['rate']})   * P4·P6·경계 칸 제외")
        print(f"- S4 발주 일치: {s4['ok']}/{s4['of']}칸 ({s4['rate']})")
        print(f"- S5 8종 과다 집계(대략치): {r['S5_over_count_proxy']}개")
        if r["wrong_cells"]:
            print("- 틀린 칸: " + ", ".join(f"{c['file']} {c['product']} (정답 {c['gt']}, 예측 {c['pred']})" for c in r["wrong_cells"]))
        if r["small_cells(P4,P6)"]:
            print("- P4·P6(별도 보고): " + ", ".join(f"{c['file']} {c['product']} ({c['gt']}→{c['pred']})" for c in r["small_cells(P4,P6)"]))
        if r["boundary_cells"]:
            print("- 경계 칸(채점 제외): " + ", ".join(f"{c['file']} {c['product']} ({c['gt']}→{c['pred']})" for c in r["boundary_cells"]))

    ev = results["eval"]
    print("\n## 성공 판정 (평가셋)")
    s1_pass = ev["S1"]["ok"] >= 10
    s2_pass = ev["S2"]["rate"] is not None and ev["S2"]["rate"] >= 0.70
    s4_pass = ev["S4"]["rate"] is not None and ev["S4"]["rate"] >= 0.80
    print(f"- S1 목표 12장 중 10장 이상: {'통과' if s1_pass else '미달'} ({ev['S1']['ok']}/12)")
    print(f"- S2 목표 70% 이상: {'통과' if s2_pass else '미달'} ({ev['S2']['rate']})")
    print(f"- S4 목표 80% 이상: {'통과' if s4_pass else '미달'} ({ev['S4']['rate']})")
    base = baseline_seconds()
    s3 = None
    if a.seconds is not None and base:
        total = sum(base)
        cut = 1 - a.seconds / total
        s3 = {"ai_seconds": a.seconds, "baseline_seconds": round(total, 2), "reduction": round(cut, 3), "pass": cut >= 0.5}
        print(f"- S3 목표 50% 이상 단축: {'통과' if s3['pass'] else '미달'} (AI {a.seconds:.1f}초 vs 기준선 {total:.2f}초, 단축 {cut*100:.1f}%, 목표 {total*0.5:.2f}초 이하)")
    elif base:
        print(f"- S3: --seconds를 주면 계산합니다 (기준선 {sum(base):.2f}초, 목표 {sum(base)*0.5:.2f}초 이하)")
    results["S3"] = s3
    results["pass"] = {"S1": s1_pass, "S2": s2_pass, "S4": s4_pass}

    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n저장: {out}")


if __name__ == "__main__":
    main()
