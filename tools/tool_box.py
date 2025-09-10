from LongVIL.tools.generate_code import GenerateCode
from LongVIL.tools.savetext import Savetext
from LongVIL.tools.add_frames import AddFrames
from LongVIL.tools.codeverify import CodeVerify
from LongVIL.tools.getplan import GetPlan
from LongVIL.tools.temporalverify import TemporalVerify
from LongVIL.tools.spatialverify import SpatialVerify

from LongVIL.tools.execute import Execute



def code_execution_tool_box(args):
    
    TOOL_LIST=[
        Savetext(resultname='Code'),
        GenerateCode(args),
        CodeVerify(args),
        Execute(args)
        ]
    return TOOL_LIST

def code_execution_noreflection_tool_box(args):
   
    TOOL_LIST=[
        Savetext(resultname='Code'),
        GenerateCode(args),
        Execute(args)
    ]
    return TOOL_LIST

def plan_tool_box_noreflection(args):   
    TOOL_LIST=[
        Savetext(resultname='Plan'),
        GetPlan(args)
    ]
    return TOOL_LIST
def plan_tool_box(args):

    TOOL_LIST=[
        AddFrames(candidate_frames=args.frames_with_hand,output=args.save_path),
        Savetext(resultname='Plan'),
        GetPlan(args),
        TemporalVerify(args),
        SpatialVerify(args)
        ]
    return TOOL_LIST