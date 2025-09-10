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
    

    for input_path, output_path in zip(input_paths, output_paths):
        image = cv2.imread(input_path)

        if image is None:
            print(f"error{input_path}")
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

class GetPlan(Tool):

    name = "GetPlan"
    description = "A tool that analyzes a sequence of video frames to recognize and describe human-object interaction actions. "
    inputs = {
    "key_frames": {
    "description": "A list of the initial keyframes of a video.",
    "type": "any",
    } ,
    }
    output_type = "any"
    base_url = 'api.deerapi.com'

    
    def __init__(self, args):
        self.obj_list=args.object_list
        self.api_key = args.api_key
        self.model_name = args.model_name
        self.video_path=args.video_path
        self.save_path=args.save_path
        self.headers =  {
                'Authorization': self.api_key, 
                'Content-Type': 'application/json'
                } 
        self.flag=False
        self.prompt = [
    "You are given a sequence of key frames from a video that shows a person manipulating objects on a tabletop. Your goal is to recognize and describe the human-object interaction actions in structured language.",
    "You will receive a list of images (frames) in time order. These frames are sampled at important moments and are not necessarily consecutive. Each frame is labeled as Frame 0, Frame 19, ..., Frame N, corresponding to their original frame IDs in the video.",
    "Your task is to analyze the changes between frames and identify the actions performed by the person.",
    f"The objects involved in the video are limited to the following list: {self.obj_list}. You must only use these object names when describing any action.",
    "Some objects may be operated several times in succession. In this case, please pay attention to the previous and next frames to determine whether the current operation is a continuous operation on the same object or a repeated frame.",
    "There are two types of actions you need to recognize:",
    "1. **Pick and Place**: A hand picks up an object and places it in a new location.",
    "2. **Open/Close Drawer**: A hand opens or closes a drawer.",
    "For pick and place actions, use the following format:",
    "-- `A hand picks up [object_A] and then places it [preposition] [object_B]. (Frames X,Y,Z...) [spatial reasoning]`",
    "Where:",
    "- [object_A] is the object being picked up.",
    "- [preposition] is one of: [\"into\", \"on top of\", \"to the left of\", \"to the right of\", \"in front of\", \"behind\"].",
    "- [object_B] is the reference object.",
    "- (Frames X,Y,Z...) indicates the key frames (from the uploaded set) where the action occurs.",
    "- [spatial reasoning] is a short explanation of the spatial relationship between the manipulated object and the reference object after the action.",
    "For open/close drawer actions, use the following format:",
    "-- `A hand opens the drawer. (Frame X,Y...) [No spatial relationship reasoning is needed for drawer actions.]`",
    "-- `A hand closes the drawer. (Frame X,Y...) [No spatial relationship reasoning is needed for drawer actions.]`",
    '''Criteria for selecting reference objects:
    - Distance priority: give priority to objects closest to the point where the object is placed.
    - Static object priority: give priority to objects that are static around the point where the object is placed, usually containers such as bowls, glass bowls, boxes, etc. 
    You can combine these two criteria to select reference objects.''',
    '''Spatial Relationship Rules:

    **Important Note on Viewpoint:**
    - The video frames are captured from a top-down (overhead) camera view.
    - In each image, the **bottom edge** of the frame corresponds to the **front edge of the table** (i.e., the side closest to the camera).
    - The **top edge** of the frame corresponds to the **back edge of the table** (i.e., the side farthest from the camera).
    - Use this orientation when interpreting spatial relations such as "in front of" and "behind".

    To avoid confusion:
    - "In front of" means the object is **closer to the bottom edge** of the frame (i.e., nearer to the camera).
    - "Behind" means the object is **closer to the top edge** of the frame (i.e., farther from the camera).


    All spatial terms (on top of, to the left of, to the right of, in front of, behind, into) must be interpreted strictly based on physical contact and relative position on the tabletop.
    - "on top of" means that one object is directly placed on the upper surface of another object, with visible physical contact between them. Simply being above or hovering over another object does not qualify as "on top of".
    - "to the left of" and "to the right of" refer to horizontal positioning on the tabletop. These terms do not require contact, only relative lateral position.
    - "in front of" and "behind" refer to depth positioning on the tabletop (i.e., closer to or farther from the front edge of the table).
    - "into" means that one object is placed inside a container (e.g., glass, bowl, box, drawer).
    - Do not use compound or diagonal descriptions (e.g., "behind and to the right of"). Choose the **single most dominant** relation from the six spatial relationships.''',
    "You must analyze the visual changes between frames to infer actions, especially when intermediate frames are missing.",
    "To help you determine the correct spatial relationship between the manipulated object and the reference object, follow these rules:",
    ''' 1. **Determine if both objects are on the same horizontal surface (i.e., the tabletop):**
    - If both objects are resting flat on the tabletop, they are considered to be on the same surface.
    - If one object is placed inside a container or on top of another object, they are not on the same surface.''',
    ''' 2. **If both objects are on the tabletop**, choose one of the following spatial relations based on their relative position:
    - **"to the left of"**: The manipulated object is horizontally to the left of the reference object.
    - **"to the right of"**: The manipulated object is horizontally to the right of the reference object.
    - **"in front of"**: The manipulated object is closer to the front edge of the table than the reference object.
    - **"behind"**: The manipulated object is farther from the front edge of the table than the reference object.''',
    ''' 3. **If the manipulated object is not on the tabletop**, determine:
    - If it is placed **inside** a container (e.g., bowl, box, drawer), use **"into"**.
    - If it is placed **on top of** another object (e.g., a block or another item), use **"on top of"**.''',
    "Each action must be described in a single line, combining the action and the spatial reasoning.",
    "Do not include any other commentary, metadata, or explanation.",
    "Your output should be a plain multi-line string, where each line follows this format:",
    '''A hand picks up banana and then places it into white bowl. (Frames 2,5) [The banana and the white bowl are not on the same surface. The banana is placed into the white bowl, which is a container.]
    A hand picks up chili and then places it to the left of white bowl. (Frames 16,38,60) [The chili and the white bowl are both on the tabletop, and the chili is to the left of the bowl.]
    A hand opens the drawer. (Frame 9) [No spatial relationship reasoning is needed for drawer actions.]
    A hand picks up carrot and then places it on top of white block. (Frames 10,33) [The carrot and the white block are not on the same surface. The carrot is placed on top of the white block. ]'''
    ]



    def forward(self,key_frames):  
        # print("yes")
        print(self.model_name)
        system_prompt = """
You are a vision-language expert specialized in analyzing human-object interactions from video frames. Your job is to identify and describe actions performed by a person manipulating objects on a tabletop, based on a sequence of key frames.

You must be precise, concise, and structured in your output. Focus on detecting pick-and-place actions and drawer interactions. For each action, include the frame range where it occurs.

In addition to the action description, you must also provide a short spatial reasoning enclosed in square brackets. This reasoning should explain the spatial relationship between the manipulated object and the reference object after the action is completed.

- If both objects are on the tabletop, describe their relative position (e.g., to the left of, behind, etc.).
- If they are not on the same surface, explain whether the object was placed into a container or on top of another object.
- For drawer actions, use: [No spatial relationship reasoning is needed for drawer actions.]

Each output must be a single line combining the action and the reasoning, in the following format:
`A hand picks up [object_A] and then places it [preposition] [object_B]. (Frames X,Y,Z...) [spatial reasoning]`

Do not include any other commentary, metadata, or explanation.
"""



        conversation_history = [{
        "role": "system",
        "content": system_prompt
        }
        ]
        
        original_image_paths=get_image_paths(self.video_path,key_frames)
        image_paths=None
        if self.flag:
            image_paths=get_keyframes_paths(original_image_paths,self.save_path)
        else:
            
            image_paths=get_keyframes_paths(original_image_paths,self.save_path)
            keyframes_pre(original_image_paths,image_paths)
            self.flag=True
        
        local_prompt = copy.deepcopy(self.prompt)
       
        user_message = {
            "role": "user",
            "content":local_prompt
        }
        
       
        for idx, frame_id in enumerate(key_frames):
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
        print("aaa",response_data)
        response_data = json.loads(response_data.decode("utf-8"))
        



        if 'choices' in response_data and len(response_data['choices']) > 0:
            assistant_message = response_data['choices'][0]['message']
            return assistant_message['content']
        else:
            print("there's wrong with the gpt output, the returned messages are: ", response_data)
            return "No available response."
          




