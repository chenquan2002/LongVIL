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
################################################################

#need to modify
from LongVIL.prompts.Planagent_prompt import system_prompt_Plan
from LongVIL.prompts.Planagent_prompt_noreflection import system_prompt_Plan_noreflection
from LongVIL.engines import get_llm_engine
from LongVIL.tools.tool_box import plan_tool_box,plan_tool_box_noreflection
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

def create_Plan_agent(args) -> ReactCodeAgent:
    llm_engine = get_llm_engine(args)
    agentsystem_prompt = system_prompt_Plan
    toollist=plan_tool_box(args)
    react_agent = ReactCodeAgent(
        llm_engine=llm_engine,
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
def create_Plan_agent_noreflection(args) -> ReactCodeAgent:
    llm_engine = get_llm_engine(args)
    agentsystem_prompt = system_prompt_Plan_noreflection
    toollist=plan_tool_box_noreflection(args)
    react_agent = ReactCodeAgent(
        llm_engine=llm_engine,
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
