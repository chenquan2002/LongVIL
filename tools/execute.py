from transformers import Tool
import pybullet
import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..'))

if project_root not in sys.path:
    sys.path.append(project_root)
from LongVIL.tools.src.env import PickPlaceEnv
from moviepy import *
import copy
import json

import re
from datetime import datetime

from argparse import Namespace




def extract_code_lines(action_sequences):
    parsed_sequences = []
    for sequence in action_sequences:
        sequence = sequence.strip()
        if "<begin_code>" in sequence and "<end_code>" in sequence:
            code_block = sequence.split("<begin_code>")[1].split("<end_code>")[0].strip()
        else:
            
            code_block = sequence

        code_lines = [line.strip() for line in code_block.split('\n') if line.strip()]
        parsed_sequences.append(code_lines)
    print(parsed_sequences)
    return parsed_sequences




def execute_sequence_statements(env, parsed_sequences):
    global_vars = {}
    pick = env.pick625
    place = env.place625
    moveto = env.moveto
    getpos = env.get_obj_pos_new
    open = env.open
    close = env.close

    errors = []

    for step_idx, code_lines in enumerate(parsed_sequences):
        
        for line in code_lines:
            line = line.strip()
            try:
                if '=' in line and 'getpos' in line:
                    var_name, expr = line.split('=', 1)
                    var_name = var_name.strip()
                    expr = expr.strip()
                    if expr.startswith("getpos(") and expr.endswith(")"):
                        inner = expr[len("getpos("):-1]
                        args = [arg.strip().strip("'\"") for arg in inner.split(',')]
                        if len(args) == 1:
                            global_vars[var_name] = getpos(args[0])
                        elif len(args) == 2:
                            global_vars[var_name] = getpos(args[0], args[1])
                        else:
                            errors.append(f"error：{line}")
                    else:
                        errors.append(f"error：{line}")

                elif line.startswith("moveto("):
                    inner = line[len("moveto("):-1].strip()
                    if inner in global_vars:
                        moveto(global_vars[inner])
                    else:
                        errors.append(f"error：{inner}")

                elif line == "pick()":
                    pick()

                elif line == "place()":
                    place()

                elif line == "open()":
                    open()

                elif line == "close()":
                    close()

                else:
                    errors.append(f"warning：{line}")

            except Exception as e:
                errors.append(f"error {line}：{e}")
    return errors



class Execute(Tool):
    name = "Execute"
    description = "A tool that executes parsed Python-like robot control code in a simulated environment."

    inputs = {
        "codelist": {
            "description": "List of Python-style robot control code blocks",
            "type": "string",
        },
    }
    output_type = "string"

    def __init__(self, args):
        super().__init__()
        self.object_dict = args.object_dict
        self.savepath = args.save_path
        if not os.path.exists(self.savepath):
            os.makedirs(self.savepath)
        self.env = PickPlaceEnv(render=True, high_res=True, high_frame_rate=False)

    def forward(self, codelist):
        _, _ = self.env.myreset(self.object_dict)
        if isinstance(codelist, str):
            codelist = [codelist]

        all_errors = []
        for code_str in codelist:
            parsed = extract_code_lines([code_str])
            errors = execute_sequence_statements(self.env, parsed)
            all_errors.extend(errors)

  
        self._render_video(os.path.join(self.savepath, "sim.mp4"))

        return "Execute Successfully!" if not all_errors else "\n".join(all_errors)

    def _render_video(self, path):
        video_clips = [ImageSequenceClip(self.env.cache_video, fps=30)]
        final_clip = concatenate_videoclips(video_clips, method="compose")
        final_clip.write_videofile(path, codec='libx264', bitrate="5000k", fps=30)



