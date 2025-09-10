import os
import json
import re
from pathlib import Path
import pandas as pd

OUTPUT_ROOT = Path("./output/data/level2")   
GT_ROOT     = Path("./data/level2")          

def normalize_code(code_blocks):
    if isinstance(code_blocks, str):
        code_blocks = [code_blocks]

    code = []
    for block in code_blocks or []:
        lines = str(block).strip().split('\n')
        for line in lines:
            line = line.replace(" = ", "=").replace("= ", "=").replace(" =", "=")
            if "getpos(" in line:
                prefix, inner = line.split("getpos(", 1)
                args = inner.rstrip(")").strip()
                if ',' in args:
                    parts = [p.strip() for p in args.split(",")]
                    args_clean = ",".join(parts)
                else:
                    args_clean = args
                line = f"{prefix}getpos({args_clean})"
            code.append(line.strip())
    return code


def normalize_line(line: str) -> str:
    line = (line or "").strip()
    line = re.sub(r"\s+", "_", line)
    line = line.replace("'", "")
    return line.lower()


def compute_prefix_match(gt_code, pred_code) -> float:
    match_len = 0
    for a, b in zip(gt_code, pred_code):
        if normalize_line(a) == normalize_line(b):
            match_len += 1
        else:
            break
    total = len(gt_code)
    return round(match_len / total, 3) if total > 0 else 0.0


def evaluate_pair(gt_path: Path, pred_path: Path):
    try:
        with gt_path.open('r', encoding='utf-8') as f1:
            gt_json = json.load(f1)
        with pred_path.open('r', encoding='utf-8') as f2:
            pred_json = json.load(f2)

        gt_code = gt_json.get("code", [])
        pred_code_blocks = pred_json.get("code", [])
        if isinstance(pred_code_blocks, list) and any("\n" in str(s) for s in pred_code_blocks):
            pred_code = normalize_code(pred_code_blocks)
        elif isinstance(pred_code_blocks, list):
            pred_code = [str(s).strip() for s in pred_code_blocks]
        elif isinstance(pred_code_blocks, str):
            pred_code = normalize_code([pred_code_blocks])
        else:
            pred_code = []

        print(gt_code)
        print(pred_code)

        ema = 1 if gt_code == pred_code else 0
        sms = compute_prefix_match(gt_code, pred_code)
        return ema, sms

    except Exception as e:
        print(f"[ERROR] while processing\n  GT   : {gt_path}\n  PRED : {pred_path}\n  → {e}")
        return None, None


def scan_results(output_root: Path):
  
    for root, _, files in os.walk(output_root):
        if "Result.json" not in files:
            continue

        pred_path = Path(root) / "Result.json"

        try:
            rel_parts = pred_path.relative_to(output_root).parts
        except ValueError:
            continue

        
        if len(rel_parts) < 3:
            continue

        case_dir   = rel_parts[0]   
        model_name = rel_parts[-2]  

        gt_path = GT_ROOT / case_dir / f"{case_dir}.json"
        yield model_name, case_dir, gt_path, pred_path


def main():
    grouped = {}  

    for model_name, case_name, gt_path, pred_path in scan_results(OUTPUT_ROOT):
        if not gt_path.exists():
            print(f"[MISS][GT  ] {gt_path}")
            continue
        if not pred_path.exists():
            print(f"[MISS][PRED] {pred_path}")
            continue

        ema, sms = evaluate_pair(gt_path, pred_path)
        if ema is None:
            continue

        grouped.setdefault(model_name, []).append({
            "file_name": case_name,
            "EMA": ema,
            "SMS": sms
        })

    if not grouped:
        print(f"No Result.json found under: {OUTPUT_ROOT}")
        return

    for model_name, rows in grouped.items():
        df = pd.DataFrame(rows)
        if df.empty:
            print(f"[WARN] No valid rows for model: {model_name}")
            continue

        avg_row = {
            "file_name": "Average",
            "EMA": round(df["EMA"].mean(), 3),
            "SMS": round(df["SMS"].mean(), 3),
        }
        df = pd.concat([df, pd.DataFrame([avg_row])], ignore_index=True)

        save_csv_path = OUTPUT_ROOT / f"{model_name}_compare_results.csv"
        df.to_csv(save_csv_path, index=False)
        print(f"\n save successfully → {save_csv_path}")
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
