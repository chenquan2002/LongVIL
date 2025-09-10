from transformers import Tool
import requests
import json
import base64
import http
import os
import copy
import cv2
import os

def add_text_to_image(image, text_positions):

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1
    thickness = 2
    line_type = cv2.LINE_AA

   
    for text, position in text_positions.items():
       
        cv2.putText(image, text, position, font, font_scale, (0, 0, 0), thickness + 2, line_type)
        cv2.putText(image, text, position, font, font_scale, (255, 255, 255), thickness, line_type)

    return image



def keyframes_pre(input_paths, output_paths):
    assert len(input_paths) == len(output_paths), "输入输出列表长度不一致"

    for input_path, output_path in zip(input_paths, output_paths):
        image = cv2.imread(input_path)

        if image is None:
            print(f"无法读取文件：{input_path}")
            continue

        height, width = image.shape[:2]

        text_positions = {
            'behind': ((width - cv2.getTextSize("behind", cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0][0]) // 2, height // 10),
            'front': ((width - cv2.getTextSize("front", cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0][0]) // 2, int(height * 0.9)),
            'left': (width // 40, (height + cv2.getTextSize("left", cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0][1]) // 2),
            'right': (int(width * 0.9), (height + cv2.getTextSize("right", cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0][1]) // 2),
        }

        processed_image=image
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, processed_image)


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
def get_keyframes_paths(original_list,output):
    return [
        os.path.join(output, "keyframes", os.path.basename(original))
        for original in original_list
    ]
def get_image_paths(video_path, frame_indices):
    
    image_paths = []
    for index in frame_indices:
        filename = f"{index:04d}.jpg"
        full_path = os.path.join(video_path, filename)
        image_paths.append(full_path)
    return image_paths
class TemporalVerify(Tool):
    name = "TemporalVerify"
    description = (
        "A tool that verifies specific actions in a short segment of video frames, based on a natural language query. It checks whether the action described in the query is actually present in the video segment."
    )
    inputs = {
        "query": {
            "description": "A natural language question or assertion to be verified, based on the video segment (e.g., 'Did the eggplant get placed to the left or right of the carrot?').",
            "type": "string"
        },
        "frames": {
            "description": "A list of ordered frames representing a short video segment, usually surrounding a potentially incorrect or ambiguous action.",
            "type": "any"
        }
    }
    output_type = "any"
    base_url = 'api.deerapi.com'

    def __init__(self, args):
        self.api_key = args.api_key
        self.model_name =  args.model_name
        self.video_path =  args.video_path
        self.save_path =  args.save_path
        self.headers = {
            'Authorization':  args.api_key,
            'Content-Type': 'application/json'
        }
        self.flag = False
        self.system_prompt = '''
        You are a video understanding assistant. You will receive a short segment in the form of sequential keyframes extracted from a video that shows a person manipulating objects on a tabletop.

        Your task is to analyze the visual evidence and answer a query about whether a specific action or spatial relationship occurred as expected. Be objective, rely only on visible evidence, and do not guess.
        '''

        self.prompt = [
        "You are given a short video segment represented by a sequence of keyframes. Your task is to analyze the video and answer the query based on visual evidence.",
        "Please follow these steps:",
        "1. Describe what happens in the video segment overall.",
        "2. Analyze each frame briefly, noting any object movement, hand interaction, or spatial changes.",
        "3. Identify the type of action: pick-and-place or drawer open/close.",
        "4. If it is a pick-and-place action, follow this reasoning process:",
        "   a. Identify the object being picked up (manipulated object).",
        "   b. Determine the most appropriate reference object based on the placement location.",
        "   c. Determine the spatial relationship between the manipulated object and the reference object.",
        "   d. Compare your analysis with the query: if the query assumes a specific reference object or spatial relation, check whether your analysis agrees or not.",
        "   e. If your analysis disagrees with the query (e.g., you think another reference object is more appropriate), explain why.",
        "5. If it is a drawer action:",
        "   - Identify whether the drawer was opened or closed.",
        "   - Determine whether the action is clearly visible and unambiguous.",
        "6. Finally, answer the query with one of: Yes / No / Unclear.",
        "7. Provide a short explanation based on your analysis, including whether the reference object and spatial relation in the query are appropriate.",

        "Use the following format for your output:",
        '''
        Video Summary:
        [Brief description of what happens in the video segment.]

        Frame-by-Frame Analysis:
        Frame X: ...
        Frame Y: ...
        ...

        Action Inference:
        - For pick-and-place:  
        A hand picks up [object_A] and then places it [preposition] [object_B]. (Frames X,Y,Z...) [spatial reasoning]

        - For drawer actions:  
        A hand opens the drawer. (Frame X,Y...) [No spatial relationship reasoning is needed for drawer actions.]  
        A hand closes the drawer. (Frame X,Y...) [No spatial relationship reasoning is needed for drawer actions.]

        Query Answer: Yes / No / Unclear  
        Explanation:  
        - If the query is fully correct (i.e., the action type, manipulated object, reference object, and spatial relation all match your analysis), answer **Yes**, and briefly explain why the query is correct.  
        - If the query contains an **ambiguous or imprecise spatial relation** (e.g., the placement is close to the reference object but not clearly aligned), answer **Unclear**, and:  
        - Explain why the spatial relation is ambiguous or unclear.  
        - Indicate the **most likely correct spatial relation** using one of the six allowed terms.  
        - If the query is incorrect (e.g., wrong spatial relation or wrong reference object), answer **No**, and:  
        - Explain what is incorrect in the query.  
        - Provide the **correct spatial relation** using one of the six allowed terms.  
        - Optionally, restate the correct action in the standard format:  
            A hand picks up [object_A] and then places it [preposition] [object_B]. (Frames X, Y, Z...) [spatial reasoning]
        ''',

        "Reference Object Selection Rules:",
        '''
        When selecting the reference object for a pick-and-place action, follow these criteria:

        1. **Distance Priority**: Prefer objects that are closest to the final location of the manipulated object.
        2. **Static Object Priority**: Prefer static objects (not moved during the action), especially containers such as bowls, boxes, or blocks.
        3. **Combine the above**: Choose the closest static object near the placement point as the reference.
        4. If no suitable reference object is nearby, or if the placement is ambiguous, state that clearly.
        ''',

        "Spatial Relationship Rules:",
        '''
        **Important Note on Viewpoint:**
        - The video frames are captured from a top-down (overhead) camera view.
        - In each image, the **bottom edge** of the frame corresponds to the **front edge of the table** (i.e., the side closest to the camera).
        - The **top edge** of the frame corresponds to the **back edge of the table** (i.e., the side farthest from the camera).
        - Use this orientation when interpreting spatial relations such as "in front of" and "behind".

        To avoid confusion:
        - "In front of" means the object is **closer to the bottom edge** of the frame (i.e., nearer to the camera).
        - "Behind" means the object is **closer to the top edge** of the frame (i.e., farther from the camera).

        1. Determine if both objects are on the same horizontal surface (i.e., the tabletop):
        - If both objects are resting flat on the tabletop, they are considered to be on the same surface.
        - If one object is placed inside a container or on top of another object, they are not on the same surface.

        2. If both objects are on the tabletop, choose one of the following spatial relations based on their relative position:
        - "to the left of": The manipulated object is horizontally to the left of the reference object.
        - "to the right of": The manipulated object is horizontally to the right of the reference object.
        - "in front of": The manipulated object is closer to the front edge of the table than the reference object. 
        - "behind": The manipulated object is farther from the front edge of the table than the reference object.

        3. Direction Selection Logic:
        - After selecting the reference object, determine whether the manipulated object and the reference object are aligned more horizontally or vertically on the tabletop.
        - If the alignment is primarily horizontal (i.e., along the left-right axis of the image), use "to the left of" or "to the right of".
        - If the alignment is primarily vertical (i.e., along the top-bottom axis of the image), use "in front of" or "behind".
        - Only one dominant spatial direction should be selected based on the stronger axis of alignment.

        4. If the manipulated object is not on the tabletop:
        - If it is placed inside a container (e.g., bowl, box, drawer), use "into".
        - If it is placed on top of another object (e.g., a block or another item), use "on top of".

        5. Do not use compound or diagonal descriptions (e.g., "behind and to the right of"). Choose the single most dominant relation. 

        6. Use visual clues (e.g., hand direction, object alignment, table edges) to determine spatial relations accurately.

        7. If there is no clear contact or alignment, or if the object is floating, being held, or partially occluded, do not assume a spatial relationship — instead, state that the relationship is unclear.

        8. Only the following six spatial relations are allowed in the output:
        - "to the left of"
        - "to the right of"
        - "in front of"
        - "behind"
        - "into"
        - "on top of"
        Do not use any other spatial terms or directional descriptions (e.g. beside, near).
        ''',
        '''Note:
        Clarification on Object Naming:
        If the object referenced in the query and the object identified in the video are clearly the same (e.g., "glass" vs. "glass bowl", or "bowl" vs. "blue bowl"), do **not** mark the query as incorrect solely due to the naming difference. Focus on the **referenced object's identity and physical location**, not on minor naming variations. Only mark it incorrect if the object is genuinely different or mismatched.

        '''
        '''Example1:
        Video Summary:
        The video segment shows a hand manipulating a purple triangular prism and interacting with other objects on a tabletop.

        Frame-by-Frame Analysis:
        - Frame 439: A hand is above the table near a purple triangular prism.
        - Frame 453: The hand is picking up the purple triangular prism.
        - Frame 477: The hand moves the purple triangular prism closer to the orange cube.
        - Frame 497: The purple triangular prism is placed on the table behind the orange cube.

        Action Inference:
        - For pick-and-place:  
        A hand picks up the purple triangular prism and then places it behind the orange cube. (Frames 453, 477, 497) [Purple triangular prism and orange cube are on the same surface. And the purple triangular prism is behind the orange cube.]

        Query Answer: Yes  
        Explanation: 
        The action described matches the query. The purple triangular prism is picked up and placed behind the orange cube as stated.
        ''',
        '''Example2:
        Video Summary:
        The video segment shows a hand moving a purple object (eggplant) near a white bowl on a tabletop.

        Frame-by-Frame Analysis:
        - Frame 182: A hand approaches and holds the purple eggplant near a white bowl.
        - Frame 227: The hand places the purple eggplant on the table close to the white bowl.

        Action Inference:
        - For pick-and-place:  
        A hand picks up the purple eggplant and then places it near the white bowl. (Frames 182, 227) [The eggplant and the bowl are on the same surface. The placement is close, but the spatial direction is ambiguous — it is not clearly behind, in front of, to the left of, or to the right of the bowl.]

        Query Answer: Unclear  
        Explanation:  
        The query asks whether the eggplant was placed **behind** the white bowl. However, the placement is close to the bowl but not clearly behind it. The spatial relation is ambiguous and does not align clearly with any of the six allowed spatial relations.  
        **The most likely spatial relation is "to the right of"**, based on the eggplant's position relative to the bowl in the top-down view.  
        **Note:** The term "beside" is not an allowed spatial relation and should not be used in the output.
        ''',
        '''Example3:
        Video Summary:  
        The video shows a hand picking up a red apple and placing it on the tabletop near a blue cup.

        Frame-by-Frame Analysis:  
        - Frame 105: A hand reaches toward the red apple.  
        - Frame 112: The hand picks up the red apple.  
        - Frame 148: The hand places the red apple on the tabletop, to the left of the blue cup (from the top-down view).  

        Action Inference:  
        - For pick-and-place:  
        A hand picks up the red apple and places it to the left of the blue cup. (Frames 112, 148)  
        [Both the apple and the cup are on the same surface.]

        Query:  
        Was the red apple placed **behind** the blue cup?

        Query Answer: No  
        Explanation:  
        The query is incorrect because the red apple was not placed **behind** the blue cup.  
        From the top-down view, the apple was placed **to the left of** the blue cup, not behind it.  
        Therefore, the correct spatial relation is **"to the left of"**.
        '''
        ]

    

    def forward(self, query, frames):
        conversation_history = [
            {
                "role": "system",
                "content": self.system_prompt
            },
        ]

        original_image_paths = get_image_paths(self.video_path, frames)
        image_paths = None

        if self.flag:
            image_paths = get_keyframes_paths(original_image_paths, self.save_path)
        else:
            image_paths = get_keyframes_paths(original_image_paths, self.save_path)
            keyframes_pre(original_image_paths, image_paths)
        local_prompt=copy.deepcopy(self.prompt)
        local_prompt.append(f"The query is: {query}. The sequence of video frames is provided below.")
        user_message = {
            "role": "user",
            "content":local_prompt
        }

        for idx, frame_id in enumerate(frames):
            encoded_img = encode_image(image_paths[idx])
            base64_url = f"data:image/jpeg;base64,{encoded_img}"
            user_message["content"].append(f"Frame {frame_id}:")  
            user_message["content"].append({
                "type": "image_url",
                "image_url": {"url": base64_url}
            })
        conversation_history.append(user_message)
      
        conn = http.client.HTTPSConnection(self.base_url)
        payload = json.dumps(
        {
            "model": self.model_name,
            "messages": conversation_history,
            "safe_mode": False
        })
       
 
        conn.request("POST", "/v1/chat/completions", payload, self.headers)
        res = conn.getresponse()
        response_data = res.read()
        
        response_data = json.loads(response_data.decode("utf-8"))
        



        if 'choices' in response_data and len(response_data['choices']) > 0:
            assistant_message = response_data['choices'][0]['message']
            return assistant_message['content']
        else:
            print("there's wrong with the gpt output, the returned messages are: ", response_data)
            return "No available response."
