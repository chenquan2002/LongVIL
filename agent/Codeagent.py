from transformers.agents import Tool, ReactCodeAgent,ReactAgent
from transformers.agents.agents import *
from transformers import is_torch_available
from transformers.utils import logging as transformers_logging
from transformers.utils.import_utils import is_pygments_available
from transformers.agents.agent_types import AgentAudio, AgentImage
from transformers.agents.default_tools import BASE_PYTHON_TOOLS, FinalAnswerTool, setup_default_tools
from transformers.agents.llm_engine import HfApiEngine, MessageRole
from transformers.agents.monitoring import Monitor
from transformers.agents.prompts import (
    DEFAULT_CODE_SYSTEM_PROMPT,
    DEFAULT_REACT_CODE_SYSTEM_PROMPT,
    DEFAULT_REACT_JSON_SYSTEM_PROMPT,
    PLAN_UPDATE_FINAL_PLAN_REDACTION,
    PROMPTS_FOR_INITIAL_PLAN,
    PROMPTS_FOR_PLAN_UPDATE,
    SUPPORTED_PLAN_TYPES,
    SYSTEM_PROMPT_FACTS,
    SYSTEM_PROMPT_FACTS_UPDATE,
    USER_PROMPT_FACTS_UPDATE,
)
from transformers.agents.python_interpreter import LIST_SAFE_MODULES, evaluate_python_code
from transformers.agents.tools import (
    DEFAULT_TOOL_DESCRIPTION_TEMPLATE,
    Tool,
    get_tool_description_with_args,
    load_tool,
)
##############################################################
from LongVIL.prompts.Codeagent_prompt import system_prompt_code
from LongVIL.prompts.Codeagent_prompt_noreflection import system_prompt_code_noreflection

from LongVIL.engines import get_llm_engine
from LongVIL.tools.tool_box import code_execution_tool_box,code_execution_noreflection_tool_box
# from HFAgent.tools.execute import Execute
# from HFAgent.tools.texttocode import TexttoCode
# from HFAgent.tools.videocaptioning_gpt import Video_captioning
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

def create_Code_agent(args) -> ReactCodeAgent:
    # kwargs->api_key, engine_path etc. 
    llm_engine = get_llm_engine(args)
    agentsystem_prompt = system_prompt_code
    toollist=code_execution_tool_box(args)
    # toollist.append(TexttoCode(object_list=args.object_list))
    # toollist.append(Execute(args.object_list, args.save_path))
    # toollist.append(Video_captioning(save_path=args.save_path, object_list=args.object_list))
    react_agent = ReactCodeAgent(
        llm_engine=llm_engine,
        # tools=TASK_SOLVING_TOOLBOX+WEB_TOOLS,
        tools=toollist,
        max_iterations=args.max_iterations,
        system_prompt=agentsystem_prompt,
        additional_authorized_imports=[
            "requests",
            "os",
            "pandas",
            "numpy",
            "torch",
            "opencv"
            "json",
            "sklearn",
            "PIL",
            "torch",
            "datetime",
            "matplotlib",
        ],
        planning_interval=None
    )
    return react_agent

def create_Code_agent_noreflection(args) -> ReactCodeAgent:
    # kwargs->api_key, engine_path etc. 
    llm_engine = get_llm_engine(args)
    agentsystem_prompt = system_prompt_code_noreflection
    toollist=code_execution_noreflection_tool_box(args)
    # toollist.append(TexttoCode(object_list=args.object_list))
    # toollist.append(Execute(args.object_list, args.save_path))
    # toollist.append(Video_captioning(save_path=args.save_path, object_list=args.object_list))
    react_agent = ReactCodeAgent(
        llm_engine=llm_engine,
        # tools=TASK_SOLVING_TOOLBOX+WEB_TOOLS,
        tools=toollist,
        max_iterations=args.max_iterations,
        system_prompt=agentsystem_prompt,
        additional_authorized_imports=[
            "requests",
            "os",
            "pandas",
            "numpy",
            "torch",
            "opencv"
            "json",
            "sklearn",
            "PIL",
            "torch",
            "datetime",
            "matplotlib",
        ],
        planning_interval=None
    )
    return react_agent

if __name__ == "__main__":
    print(1)
