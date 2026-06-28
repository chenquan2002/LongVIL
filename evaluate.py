import argparse
import ast
import copy
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


AUTOSTACK_ON_COLLISION = True

DIRECTION_MAP = {
    "front": (1, 0),
    "behind": (-1, 0),
    "left": (0, -1),
    "right": (0, 1),
    "top": (0, 0),
    "into": (0, 0),
}


def is_primitive_line(line: str) -> bool:
    return (
        ("=" in line and "getpos(" in line)
        or (line.startswith("moveto(") and line.endswith(")"))
        or line in {"pick()", "place()", "open()", "close()"}
    )


def normalize_code(code_blocks: Any) -> List[str]:
    if code_blocks is None:
        return []
    if isinstance(code_blocks, str):
        code_blocks = [code_blocks]

    code: List[str] = []
    for block in code_blocks or []:
        text = str(block)
        text = text.replace("<begin_code>", "").replace("<end_code>", "")
        text = re.sub(r"```(?:python|py)?", "", text)
        text = text.replace("```", "")
        for raw_line in text.strip().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            line = re.sub(r"\s*=\s*", "=", line)
            if "getpos(" in line:
                prefix, inner = line.split("getpos(", 1)
                args = inner.rstrip(")").strip()
                if "," in args:
                    args_clean = ",".join(part.strip() for part in args.split(","))
                else:
                    args_clean = args
                line = f"{prefix}getpos({args_clean})"
            if is_primitive_line(line):
                code.append(line)
    return code


def normalize_line(line: str) -> str:
    line = (line or "").strip()
    line = re.sub(r"\s+", "_", line)
    line = line.replace("'", "").replace('"', "")
    return line.lower()


def compute_prefix_match(gt_code: List[str], pred_code: List[str]) -> float:
    match_len = 0
    for gt_line, pred_line in zip(gt_code, pred_code):
        if normalize_line(gt_line) == normalize_line(pred_line):
            match_len += 1
        else:
            break
    total = len(gt_code)
    return round(match_len / total, 3) if total > 0 else 0.0


def coord_to_grid(x: float, y: float) -> List[int]:
    return [int(y / 0.1), int(x / 0.1)]


def build_initial_state(gt_json: dict) -> Dict[str, Dict[str, Any]]:
    object_states: Dict[str, Dict[str, Any]] = {}
    pre_actions = gt_json.get("pre_action_sequences")
    for obj in gt_json["object_list"]:
        pos = gt_json["positions"][obj]
        is_drawer = "drawer" in obj
        object_states[obj] = {
            "position": coord_to_grid(pos["x"], pos["y"]),
            "on_top_of": None,
            "top_object": None,
            "held": False,
            "open_state": "open" if (is_drawer and pre_actions) else ("closed" if is_drawer else None),
        }
    return object_states


class CodeExecutor:
    def __init__(self, initial_states: Dict[str, Dict[str, Any]]):
        self.object_states = copy.deepcopy(initial_states)
        self.last_target: Optional[Tuple[str, Optional[str]]] = None
        self.held_object: Optional[str] = None

    def _objects_at_pos(self, pos: List[int]) -> List[str]:
        return [name for name, state in self.object_states.items() if state["position"] == pos]

    def _stack_top_at(self, pos: List[int]) -> Optional[str]:
        candidates = self._objects_at_pos(pos)
        if not candidates:
            return None

        tops = []
        for obj in candidates:
            cur = obj
            while self.object_states[cur]["top_object"] is not None:
                cur = self.object_states[cur]["top_object"]
            tops.append(cur)
        return sorted(set(tops))[0] if tops else None

    def _getpos(self, obj: str, direction: Optional[str] = None) -> List[int]:
        if obj not in self.object_states:
            raise RuntimeError(f"getpos target does not exist: {obj}")
        base = self.object_states[obj]["position"]
        if direction is None:
            return base
        if direction not in DIRECTION_MAP:
            raise ValueError(f"Unknown direction: {direction}")
        dx, dy = DIRECTION_MAP[direction]
        return [base[0] + dx, base[1] + dy]

    def _pick(self) -> None:
        if not self.last_target:
            raise RuntimeError("pick called without a target")
        obj, _ = self.last_target
        if obj not in self.object_states:
            raise RuntimeError(f"pick target does not exist: {obj}")

        self.object_states[obj]["held"] = True
        self.held_object = obj
        under = self.object_states[obj]["on_top_of"]
        if under:
            self.object_states[under]["top_object"] = None
        self.object_states[obj]["on_top_of"] = None

    def _place(self) -> None:
        if self.held_object is None or not self.last_target:
            raise RuntimeError("No object to place or target not set")

        obj = self.held_object
        target_obj, direction = self.last_target
        if target_obj not in self.object_states:
            raise RuntimeError(f"place target does not exist: {target_obj}")

        if direction in {"top", "into"}:
            self.object_states[obj]["position"] = self.object_states[target_obj]["position"]
            if direction == "into":
                target_open_state = self.object_states[target_obj]["open_state"]
                if target_open_state is not None and target_open_state != "open":
                    raise RuntimeError(f"Cannot place into closed drawer: {target_obj}")
            self.object_states[obj]["on_top_of"] = target_obj
            self.object_states[target_obj]["top_object"] = obj
        else:
            new_pos = self._getpos(target_obj, direction)
            self.object_states[obj]["position"] = new_pos
            if AUTOSTACK_ON_COLLISION:
                top_here = self._stack_top_at(new_pos)
                if top_here is not None and top_here != obj:
                    under = self.object_states[obj]["on_top_of"]
                    if under:
                        self.object_states[under]["top_object"] = None
                    self.object_states[obj]["on_top_of"] = top_here
                    self.object_states[top_here]["top_object"] = obj

        self.object_states[obj]["held"] = False
        self.held_object = None

    def _open(self) -> None:
        for state in self.object_states.values():
            if state["open_state"] is not None:
                state["open_state"] = "open"

    def _close(self) -> None:
        for state in self.object_states.values():
            if state["open_state"] is not None:
                state["open_state"] = "closed"

    @staticmethod
    def _parse_getpos(expr: str) -> Tuple[str, Optional[str]]:
        node = ast.parse(expr, mode="eval").body
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "getpos":
            raise RuntimeError(f"Invalid getpos expression: {expr}")
        if len(node.args) not in {1, 2}:
            raise RuntimeError(f"getpos expects one or two arguments: {expr}")
        values = []
        for arg in node.args:
            if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                raise RuntimeError(f"getpos arguments must be string literals: {expr}")
            values.append(arg.value)
        return values[0], values[1] if len(values) == 2 else None

    def run_code(self, code_lines: List[str]) -> Dict[str, Dict[str, Any]]:
        var_map: Dict[str, Tuple[str, Optional[str]]] = {}
        for line in code_lines:
            line = line.strip()
            if not line:
                continue

            if "=" in line and "getpos(" in line:
                var_name, expr = line.split("=", 1)
                target = self._parse_getpos(expr.strip())
                var_map[var_name.strip()] = target
                self.last_target = target
                continue

            if line.startswith("moveto(") and line.endswith(")"):
                var = line[len("moveto("):-1].strip()
                if var not in var_map:
                    raise RuntimeError(f"moveto variable not defined: {var}")
                self.last_target = var_map[var]
                continue

            if line == "pick()":
                self._pick()
                continue
            if line == "place()":
                self._place()
                continue
            if line == "open()":
                self._open()
                continue
            if line == "close()":
                self._close()
                continue

            raise RuntimeError(f"Unknown code line: {line}")

        return self.object_states


def compare_states(
    states_a: Dict[str, Dict[str, Any]],
    states_b: Dict[str, Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    diffs: List[str] = []
    keys_a = set(states_a.keys())
    keys_b = set(states_b.keys())

    if keys_a != keys_b:
        if keys_a - keys_b:
            diffs.append(f"Objects only in reference: {sorted(keys_a - keys_b)}")
        if keys_b - keys_a:
            diffs.append(f"Objects only in prediction: {sorted(keys_b - keys_a)}")

    for obj in sorted(keys_a & keys_b):
        ref_state = states_a[obj]
        pred_state = states_b[obj]
        for field in ["position", "on_top_of", "top_object", "held", "open_state"]:
            if ref_state.get(field) != pred_state.get(field):
                diffs.append(f"{obj}.{field}: ref={ref_state.get(field)} pred={pred_state.get(field)}")

    return len(diffs) == 0, diffs


def evaluate_pair(gt_path: Path, pred_path: Path) -> Dict[str, Any]:
    with gt_path.open("r", encoding="utf-8") as f:
        gt_json = json.load(f)
    with pred_path.open("r", encoding="utf-8") as f:
        pred_json = json.load(f)

    gt_code = normalize_code(gt_json.get("code", []))
    pred_code = normalize_code(pred_json.get("code", []))

    ema = 1 if gt_code == pred_code else 0
    sms = compute_prefix_match(gt_code, pred_code)

    initial_states = build_initial_state(gt_json)
    ref_final = CodeExecutor(initial_states).run_code(gt_code)
    pred_final = CodeExecutor(initial_states).run_code(pred_code)
    equal, diffs = compare_states(ref_final, pred_final)

    return {
        "EMA": ema,
        "SMS": sms,
        "FSA": 1 if equal else 0,
        "diffs": "; ".join(diffs),
    }


def infer_task_id_from_pred(pred_path: Path) -> Tuple[str, str]:
    case_dir = pred_path.parent.parent.name
    if case_dir.endswith("_clean"):
        return case_dir[:-len("_clean")], "clean"
    if case_dir.endswith("_complex"):
        return case_dir[:-len("_complex")], "complex"
    return case_dir, "unknown"


def find_gt_json(gt_root: Path, task_id: str) -> Optional[Path]:
    candidates = [
        gt_root / task_id / f"{task_id}.json",
        gt_root / task_id / "example.json",
        gt_root / f"{task_id}.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    task_dir = gt_root / task_id
    if task_dir.is_dir():
        json_files = sorted(task_dir.glob("*.json"))
        if len(json_files) == 1:
            return json_files[0]
    return None


def evaluate_single(gt_json: Path, pred_json: Path, save_csv: Optional[Path]) -> List[Dict[str, Any]]:
    result = evaluate_pair(gt_json, pred_json)
    row = {
        "task_id": gt_json.stem,
        "data_type": "single",
        "gt_path": str(gt_json),
        "pred_path": str(pred_json),
        "status": "ok",
        "EMA": result["EMA"],
        "SMS": result["SMS"],
        "FSA": result["FSA"],
        "error": "",
        "diffs": result["diffs"],
    }
    rows = add_average_row([row])
    output_path = save_csv or pred_json.parent / "compare_results.csv"
    write_csv(rows, output_path)
    return rows


def evaluate_batch(
    gt_root: Path,
    pred_root: Path,
    save_csv: Path,
    data_type: str = "all",
    model_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    pred_files = sorted(pred_root.rglob("Result.json"))
    rows: List[Dict[str, Any]] = []

    for pred_path in pred_files:
        if model_dir and pred_path.parent.name != model_dir:
            continue

        inferred_task_id, inferred_data_type = infer_task_id_from_pred(pred_path)
        if data_type != "all" and inferred_data_type != data_type:
            continue

        task_dir_id = pred_path.parent.parent.parent.name
        task_id_candidates = []
        for candidate in [inferred_task_id, task_dir_id]:
            if candidate and candidate not in task_id_candidates:
                task_id_candidates.append(candidate)

        gt_path = None
        task_id = inferred_task_id
        for candidate in task_id_candidates:
            gt_path = find_gt_json(gt_root, candidate)
            if gt_path is not None:
                task_id = candidate
                break

        if gt_path is None:
            rows.append({
                "task_id": inferred_task_id,
                "data_type": inferred_data_type,
                "gt_path": "",
                "pred_path": str(pred_path),
                "status": "missing_gt",
                "EMA": "",
                "SMS": "",
                "FSA": "",
                "error": f"Cannot find GT json for candidates={task_id_candidates}",
                "diffs": "",
            })
            continue

        try:
            result = evaluate_pair(gt_path, pred_path)
            rows.append({
                "task_id": task_id,
                "data_type": inferred_data_type,
                "gt_path": str(gt_path),
                "pred_path": str(pred_path),
                "status": "ok",
                "EMA": result["EMA"],
                "SMS": result["SMS"],
                "FSA": result["FSA"],
                "error": "",
                "diffs": result["diffs"],
            })
        except Exception as exc:
            rows.append({
                "task_id": task_id,
                "data_type": inferred_data_type,
                "gt_path": str(gt_path),
                "pred_path": str(pred_path),
                "status": "error",
                "EMA": "",
                "SMS": "",
                "FSA": "",
                "error": str(exc),
                "diffs": "",
            })

    rows = add_average_row(rows)
    write_csv(rows, save_csv)
    return rows


def add_average_row(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    if not ok_rows:
        return rows

    def mean_metric(name: str) -> float:
        return round(sum(float(row[name]) for row in ok_rows) / len(ok_rows), 3)

    rows.append({
        "task_id": "Average",
        "data_type": "",
        "gt_path": "",
        "pred_path": "",
        "status": f"{len(ok_rows)} evaluated",
        "EMA": mean_metric("EMA"),
        "SMS": mean_metric("SMS"),
        "FSA": mean_metric("FSA"),
        "error": "",
        "diffs": "",
    })
    return rows


def write_csv(rows: List[Dict[str, Any]], save_csv: Path) -> None:
    save_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["task_id", "data_type", "status", "EMA", "SMS", "FSA", "gt_path", "pred_path", "error", "diffs"]
    with save_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def print_summary(rows: List[Dict[str, Any]], save_csv: Path) -> None:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    error_rows = [row for row in rows if row.get("status") not in {"ok"} and row.get("task_id") != "Average"]
    average = rows[-1] if rows and rows[-1].get("task_id") == "Average" else None

    print(f"Saved results to: {save_csv}")
    print(f"Evaluated tasks: {len(ok_rows)}")
    if error_rows:
        print(f"Skipped/error tasks: {len(error_rows)}")
    if average:
        print(f"Average EMA: {average['EMA']}")
        print(f"Average SMS: {average['SMS']}")
        print(f"Average FSA: {average['FSA']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate LongVIL predictions with EMA, SMS, and FSA.")
    single = parser.add_argument_group("Single-task evaluation")
    single.add_argument("--gt_json", type=Path, help="Path to one ground-truth task JSON file.")
    single.add_argument("--pred_json", type=Path, help="Path to one predicted Result.json file.")

    batch = parser.add_argument_group("Batch evaluation")
    batch.add_argument("--gt_root", type=Path, help="Root directory containing benchmark task JSON files.")
    batch.add_argument("--pred_root", type=Path, help="Root directory containing predicted Result.json files.")
    batch.add_argument("--data_type", choices=["all", "clean", "complex"], default="all")
    batch.add_argument("--model_dir", type=str, help="Optional model output directory name, e.g. gpt-4o-gpt-4o.")

    parser.add_argument("--save_csv", type=Path, help="Where to save the evaluation CSV.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.gt_json or args.pred_json:
        if not args.gt_json or not args.pred_json:
            raise SystemExit("Single-task mode requires both --gt_json and --pred_json.")
        if not args.gt_json.exists():
            raise SystemExit(f"Ground-truth JSON not found: {args.gt_json}")
        if not args.pred_json.exists():
            raise SystemExit(f"Prediction JSON not found: {args.pred_json}")

        save_csv = args.save_csv or args.pred_json.parent / "compare_results.csv"
        rows = evaluate_single(args.gt_json, args.pred_json, save_csv)
        print_summary(rows, save_csv)
        return

    if not args.gt_root or not args.pred_root:
        raise SystemExit("Batch mode requires --gt_root and --pred_root, or use --gt_json and --pred_json for one task.")
    if not args.gt_root.exists():
        raise SystemExit(f"Ground-truth root not found: {args.gt_root}")
    if not args.pred_root.exists():
        raise SystemExit(f"Prediction root not found: {args.pred_root}")

    save_csv = args.save_csv or args.pred_root / "evaluation_results.csv"
    rows = evaluate_batch(args.gt_root, args.pred_root, save_csv, args.data_type, args.model_dir)
    print_summary(rows, save_csv)


if __name__ == "__main__":
    main()
