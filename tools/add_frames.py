from transformers import Tool
import numpy as np
import json
from typing import List, Optional
class AddFrames(Tool):

    name = "AddFrames"
    description = "A tool enhances a sparse list of keyframes by inserting additional frames from a candidate pool, only when there are large gaps between original frames."

    inputs = {
    "original_key_frames": {
    "description": "A list of the initial keyframes of a video.",
    "type": "any",
    } ,
    
    }
    output_type = "any"

    def __init__(self,candidate_frames=None,output=None):
        super().__init__()
        self.candidate_frames=candidate_frames
        self.output=output
    import numpy as np

    def compute_statistical_threshold(self,intervals):
        q1 = np.percentile(intervals, 25)
        q3 = np.percentile(intervals, 75)
        iqr = q3 - q1
        threshold = q3 + 1.5 * iqr
        return threshold

    def forward(self,original_key_frames:Optional[List[int]] =None):
        if len(original_key_frames) < 2:
            return original_key_frames

       
        intervals = [original_key_frames[i+1] - original_key_frames[i] for i in range(len(original_key_frames) - 1)]
        median_interval = np.median(intervals)
        threshold_multiplier=1.8
    
       
        result_frames = set(original_key_frames)

        
        for i in range(len(original_key_frames) - 1):
            start = original_key_frames[i]
            end = original_key_frames[i + 1]
            gap = end - start

            if gap > median_interval * threshold_multiplier or gap>100:
                
                mid_value1 = start + gap // 3
                mid_value2 = start + 2 * gap // 3   
              
               
                valid_candidates = [f for f in self.candidate_frames if start < f < end]
                if not valid_candidates:
                    continue
                
                closest1 = min(valid_candidates, key=lambda x: abs(x - mid_value1))
                result_frames.add(closest1)
                closest2 = min(valid_candidates, key=lambda x: abs(x - mid_value2))
                result_frames.add(closest2)
                  
        result_frames=list(result_frames)
        with open(f"{self.output}/aug_keyframelist.json", "w", encoding="utf-8") as f:
            json.dump(result_frames, f, indent=4)
        return sorted(result_frames)

        

