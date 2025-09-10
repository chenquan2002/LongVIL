import argparse
import sys
import os
import warnings
import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
from setproctitle import setproctitle
from moviepy import VideoFileClip

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from LongVIL.agent.Planagent import create_Plan_agent, create_Plan_agent_noreflection
from LongVIL.agent.Codeagent import create_Code_agent, create_Code_agent_noreflection

warnings.filterwarnings("ignore")

def createpath(args, dir_action=None):
    formatted_time = f"{args.llm_model_name}-{args.model_name}"
    full_path = f"{args.output}/{dir_action}/{formatted_time}"
    os.makedirs(full_path, exist_ok=True)
    return full_path


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine_type", required=True, choices=["deepseekv3", "gpt"], help="Engine you want to use.")
    parser.add_argument("--model_name", required=True, help="The specific model you want to use")
    parser.add_argument("--llm_model_name", required=True, help="The specific LLM model you want to use")
    parser.add_argument("--api_key", help="The api key to load api engine. If you use api engine, This param must be provided.")
    parser.add_argument("--service_type", choices=["deerapi", "api2d"], help="gpt service type.")
    parser.add_argument("--max_iterations", default=30, help="Max iterations for agent.")
    parser.add_argument('--frame_path', type=str,required=True, help='The path to locate keyframe and frames_with_hand')
    parser.add_argument('--keyframe', type=str, help='List of key frame indexes')
    parser.add_argument('--frames_with_hand_path', type=str, help='List of all frames with hand')
    parser.add_argument('--output', type=str, required=True, help='Path to output')
    parser.add_argument('--data_json', type=str, required=True, help='Config file')
    parser.add_argument('--data_type', type=str, required=True, help='Type of data(clean or complex)')
    parser.add_argument('--use_reflection', type=str, choices=['y', 'n'], default='y',
                        help="Use reflection agents (y) or noreflection agents (n).")

    return parser.parse_args()


def main():
    args = get_args()
    args.video_path = None
    args.object_list = None

    if args.data_type == 'clean':
        args.keyframe = f"{args.frame_path}_clean/keyframelist.json"
        args.frames_with_hand_path = f"{args.frame_path}_clean/frames_with_hand.json"
    else:
        args.keyframe = f"{args.frame_path}_complex/keyframelist.json"
        args.frames_with_hand_path = f"{args.frame_path}_complex/frames_with_hand.json"

    try:
        with open(f'{args.data_json}', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if args.data_type == 'clean':
                args.video_path = f"{args.frame_path}_clean/frames"
                dirname = f"{args.frame_path}_clean"
            else:
                args.video_path = f"{args.frame_path}_complex/frames"
                dirname = f"{args.frame_path}_complex"
            args.object_list = data['object_list']
            args.object_dict = data['positions']
    except FileNotFoundError:
        print(f"{args.data_json} not found.")

    args.save_path = createpath(args, dir_action=dirname)
    print("savepath", args.save_path)

    try:
        with open(f'{args.keyframe}', 'r', encoding='utf-8') as f:
            args.key_frames = json.load(f)
    except FileNotFoundError:
        print(f"error. {args.keyframe}not found")
        args.key_frames = None

    try:
        with open(f'{args.frames_with_hand_path}', 'r', encoding='utf-8') as f:
            args.frames_with_hand = json.load(f)
    except FileNotFoundError:
        print(f"error. {args.frames_with_hand_path}not found")
        args.frames_with_hand = None

    print("Available objects:", args.object_list)

    if args.use_reflection == 'y':
        Planagent = create_Plan_agent(args)
        Codeagent = create_Code_agent(args)
    else:
        Planagent = create_Plan_agent_noreflection(args)
        Codeagent = create_Code_agent_noreflection(args)

    Planagent.run(
        "You will be given a list of keyframes of a video (parameter key_frames). "
        "Parameter object_list represents the name of the object appearing in the video. "
        "The parameter save_path indicates the path where the results are saved. "
        "Please analyzes the sequence of video frames to recognize and describe human-object interaction actions as required.",
        key_frames=args.key_frames,
        object_list=args.object_list,
        save_path=args.save_path
    )

    Planlogs = Planagent.write_inner_memory_from_logs()
    with open(f'{args.save_path}/Planlogs.json', 'w', encoding='utf-8') as f:
        json.dump(Planlogs, f, ensure_ascii=False, indent=4)

 
    with open(f'{args.save_path}/Result.json', 'r') as f:
        data = json.load(f)
    action_list = data['action_sequences']

    Codeagent.run(
        "You will be given a action list. Parameter action_list represents the sequence of actions you need to process. "
        "The parameter save_path indicates the path where the results are saved. "
        "Please perform code conversion, execution and result verification as required.",
        action_list=action_list,
        save_path=args.save_path
    )

    Codelogs = Codeagent.write_inner_memory_from_logs()
    with open(f'{args.save_path}/Codelogs.json', 'w', encoding='utf-8') as f:
        json.dump(Codelogs, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
