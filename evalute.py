import os
import json
import re
from pathlib import Path
import pandas as pd
import copy
from typing import List, Dict, Optional, Tuple, Any

OUTPUT_ROOT = Path("./output/data/example")
GT_ROOT     = Path("./data/example")

# ============== Configs ==============
# Auto-stack when placing into a cell that already has objects (for non top/into placements)
AUTOSTACK_ON_COLLISION = True

# ============== Normalizers (yours) ==============
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

# ============== Soft match & EMA (yours) ==============
def compute_prefix_match(gt_code, pred_code) -> float:
    match_len = 0
    for a, b in zip(gt_code, pred_code):
        if normalize_line(a) == normalize_line(b):
            match_len += 1
        else:
            break
    total = len(gt_code)
    return round(match_len / total, 3) if total > 0 else 0.0

# ============== Final-state engine (new) ==============
# coord -> grid (unbounded), origin at bottom-left, step 0.1
def coord_to_grid(x: float, y: float) -> List[int]:
    row = int(y / 0.1)
    col = int(x / 0.1)
    return [row, col]

DIRECTION_MAP = {
    "front": (1, 0),
    "behind": (-1, 0),
    "left": (0, -1),
    "right": (0, 1),
    "top": (0, 0),   # same cell + stacking relation
    "into": (0, 0),  # same cell + container; drawer must be open
}

def build_initial_state_from_A(jsonA: dict) -> Dict[str, Dict[str, Any]]:
    """
    Build initial object states from GT json (A):
      position: [row, col] from coord_to_grid
      on_top_of/top_object: None
      held: False
      open_state: 'open'/'closed' for drawer objects, else None
        (drawer initial = 'open' iff pre_action_sequences is not None)
    """
    object_states: Dict[str, Dict[str, Any]] = {}
    pre = jsonA.get("pre_action_sequences")
    for obj in jsonA["object_list"]:
        pos = jsonA["positions"][obj]
        grid_pos = coord_to_grid(pos["x"], pos["y"])
        is_drawer = "drawer" in obj
        object_states[obj] = {
            "position": grid_pos,
            "on_top_of": None,
            "top_object": None,
            "held": False,
            "open_state": ("open" if (is_drawer and pre) else ("closed" if is_drawer else None)),
        }
    return object_states

class CodeExecutor:
    def __init__(self, initial_states: Dict[str, Dict[str, Any]]):
        self.object_states = copy.deepcopy(initial_states)
        self.last_target: Optional[Tuple[str, Optional[str]]] = None
        self.held_object: Optional[str] = None

    # helpers for autostack
    def _objects_at_pos(self, pos: List[int]):
        return [name for name, st in self.object_states.items() if st["position"] == pos]

    def _stack_top_at(self, pos: List[int]):
        """
        Return the top-most object in the cell (following 'top_object' chains).
        If multiple disjoint stacks exist (unlikely), pick the lexicographically smallest top for determinism.
        """
        candidates = self._objects_at_pos(pos)
        if not candidates:
            return None
        tops = []
        for obj in candidates:
            cur = obj
            while self.object_states[cur]["top_object"] is not None:
                cur = self.object_states[cur]["top_object"]
            tops.append(cur)
        tops = sorted(set(tops))
        return tops[0] if tops else None

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

    def _pick(self):
        if not self.last_target:
            raise RuntimeError("pick called without a target (missing moveto/getpos)")
        obj, _ = self.last_target
        if obj not in self.object_states:
            raise RuntimeError(f"pick target does not exist: {obj}")
        self.object_states[obj]["held"] = True
        self.held_object = obj
        under = self.object_states[obj]["on_top_of"]
        if under:
            self.object_states[under]["top_object"] = None
        self.object_states[obj]["on_top_of"] = None

    def _place(self):
        if self.held_object is None or not self.last_target:
            raise RuntimeError("No object to place or target not set")
        obj = self.held_object
        target_obj, direction = self.last_target
        if target_obj not in self.object_states:
            raise RuntimeError(f"place target does not exist: {target_obj}")

        if direction in {"top", "into"}:
            # same cell as target
            self.object_states[obj]["position"] = self.object_states[target_obj]["position"]
            if direction == "into":
                if self.object_states[target_obj]["open_state"] != "open":
                    raise RuntimeError(f"Cannot place into closed drawer: {target_obj}")
            self.object_states[obj]["on_top_of"] = target_obj
            self.object_states[target_obj]["top_object"] = obj
        else:
            # directional offset
            new_pos = self._getpos(target_obj, direction)
            self.object_states[obj]["position"] = new_pos

            # auto-stack on collision (optional)
            if AUTOSTACK_ON_COLLISION:
                top_here = self._stack_top_at(new_pos)
                if top_here is not None and top_here != obj:
                    # detach existing relation, then stack on top
                    under = self.object_states[obj]["on_top_of"]
                    if under:
                        self.object_states[under]["top_object"] = None
                    self.object_states[obj]["on_top_of"] = top_here
                    self.object_states[top_here]["top_object"] = obj

        self.object_states[obj]["held"] = False
        self.held_object = None

    def _open(self):
        for state in self.object_states.values():
            if state["open_state"] is not None:
                state["open_state"] = "open"

    def _close(self):
        for state in self.object_states.values():
            if state["open_state"] is not None:
                state["open_state"] = "closed"

    def run_code(self, code_lines: List[str]) -> Dict[str, Dict[str, Any]]:
        var_map: Dict[str, Tuple[str, Optional[str]]] = {}
        for raw in code_lines:
            line = raw.strip()
            if not line:
                continue

            if "=" in line and "getpos" in line:
                var_name, right = line.split("=", 1)
                var_name = var_name.strip()
                right_stripped = right.strip()
                if "," in right_stripped:
                    parts = right_stripped.split(",")
                    obj = parts[0].split("'")[1]
                    direction = parts[1].split("'")[1]
                else:
                    obj = right_stripped.split("'")[1]
                    direction = None
                var_map[var_name] = (obj, direction)
                self.last_target = (obj, direction)
                continue

            if line.startswith("moveto(") and line.endswith(")"):
                var = line[line.find("(")+1:line.rfind(")")]
                if var not in var_map:
                    raise RuntimeError(f"moveto variable not defined: {var}")
                self.last_target = var_map[var]
                continue

            if line == "pick()":
                self._pick();  continue
            if line == "place()":
                self._place(); continue
            if line == "open()":
                self._open();  continue
            if line == "close()":
                self._close(); continue

            # ignore unknown lines (or raise in strict mode)
            # raise RuntimeError(f"Unknown line: {line}")

        return self.object_states

def compare_states(statesA: Dict[str, Dict[str, Any]],
                   statesB: Dict[str, Dict[str, Any]]) -> Tuple[bool, List[str]]:
    diffs: List[str] = []
    keysA = set(statesA.keys())
    keysB = set(statesB.keys())
    if keysA != keysB:
        onlyA = keysA - keysB
        onlyB = keysB - keysA
        if onlyA:
            diffs.append(f"Objects only in A: {sorted(list(onlyA))}")
        if onlyB:
            diffs.append(f"Objects only in B: {sorted(list(onlyB))}")

    for obj in sorted(keysA & keysB):
        a = statesA[obj]
        b = statesB[obj]
        for field in ["position", "on_top_of", "top_object", "held", "open_state"]:
            if a.get(field) != b.get(field):
                diffs.append(f"{obj} differs in {field}: A={a.get(field)} vs B={b.get(field)}")

    return (len(diffs) == 0), diffs

# ============== Pair evaluation (now returns EMA, SMS, FSA) ==============
def evaluate_pair(gt_path: Path, pred_path: Path):
    try:
        with gt_path.open('r', encoding='utf-8') as f1:
            gt_json = json.load(f1)
        with pred_path.open('r', encoding='utf-8') as f2:
            pred_json = json.load(f2)

        # ---- EMA / SMS (text-level) ----
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

        # Optionally expand GT if any line has \n (rare)
        if isinstance(gt_code, list) and any("\n" in str(s) for s in gt_code):
            gt_code_for_text = normalize_code(gt_code)
        else:
            gt_code_for_text = [str(s).strip() for s in gt_code]

        ema = 1 if gt_code_for_text == pred_code else 0
        sms = compute_prefix_match(gt_code_for_text, pred_code)

        # ---- FSA (state-level) ----
        # init from GT json (A)
        initial_states = build_initial_state_from_A(gt_json)

        # A.code: use as-is (unless has \n then expand)
        code_lines_A = gt_code if not any("\n" in str(s) for s in gt_code) else normalize_code(gt_code)
        # B.code: normalized already in pred_code
        code_lines_B = pred_code

        execA = CodeExecutor(initial_states)
        finalA = execA.run_code(code_lines_A)

        execB = CodeExecutor(initial_states)
        finalB = execB.run_code(code_lines_B)

        equal, diffs = compare_states(finalA, finalB)
        fsa = 1 if equal else 0

        # Optional debug:
        # print(gt_code_for_text); print(pred_code); print("FSA diffs:", diffs)

        return ema, sms, fsa

    except Exception as e:
        print(f"[ERROR] while processing\n  GT   : {gt_path}\n  PRED : {pred_path}\n  → {e}")
        return None, None, None

# ============== Scanning outputs (yours, minor tweaks) ==============
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

        case_dir   = rel_parts[0]   # e.g., level2_xxx
        model_name = rel_parts[-2]  # parent dir name as model

        gt_path = GT_ROOT / case_dir / f"{case_dir}.json"
        yield model_name, case_dir, gt_path, pred_path

# ============== Main (prints and CSV with EMA, SMS, FSA) ==============
def main():
    grouped = {}

    for model_name, case_name, gt_path, pred_path in scan_results(OUTPUT_ROOT):
        if not gt_path.exists():
            print(f"[MISS][GT  ] {gt_path}")
            continue
        if not pred_path.exists():
            print(f"[MISS][PRED] {pred_path}")
            continue

        ema, sms, fsa = evaluate_pair(gt_path, pred_path)
        if ema is None:
            continue

        grouped.setdefault(model_name, []).append({
            "file_name": case_name,
            "EMA": ema,
            "SMS": sms,
            "FSA": fsa
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
            "FSA": round(df["FSA"].mean(), 3),
        }
        df = pd.concat([df, pd.DataFrame([avg_row])], ignore_index=True)

        save_csv_path = OUTPUT_ROOT / f"{model_name}_compare_results.csv"
        df.to_csv(save_csv_path, index=False)
        print(f"\nsave successfully → {save_csv_path}")
        print(df.to_string(index=False))

if __name__ == "__main__":
    main()
