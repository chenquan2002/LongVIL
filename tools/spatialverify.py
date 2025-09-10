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
            print(f"not found{input_path}")
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
class SpatialVerify(Tool):
    name = "SpatialVerify"
    description = "Determines the spatial relationship between two objects in an image based on top-down view rules."
    inputs = {
        "query": {
            "description": "A question about the spatial relationship between two objects.",
            "type": "string"
        },
        "frame": {
            "description": "An image showing the objects.",
            "type": "any"
        }
    }

    output_type = "any"
    base_url = 'api.deerapi.com'

    def __init__(self, args):
        self.api_key = args.api_key
        self.model_name = args.model_name
        self.video_path = args.video_path
        self.save_path = args.save_path
        self.headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json'
        }
        self.flag = False
        self.system_prompt = '''
You are a spatial reasoning assistant. You will receive a single image (a top-down keyframe from a tabletop video) and a query that asks about the spatial relationship between two objects in the image.

Your task is to determine the most likely spatial relationship between the two mentioned objects based solely on their positions in the image. Do not consider any temporal or action-related information. Focus only on the spatial arrangement in this single frame.

You must return a single, complete English sentence that describes the spatial relationship, such as:
- "The purple block is behind the green block."
- "The red cylinder is to the left of the blue cube."
- "The yellow ball is on top of the white box."
- "The blue block is inside the red bowl."

Even if the spatial relationship is somewhat ambiguous, you must still choose the most likely direction based on the visual evidence. Do not return "unclear" or similar responses.

Do not provide any explanation or reasoning. Only return the final sentence.
'''


        self.prompt = [
    "Please follow these spatial reasoning rules:",

    '''
    Spatial Relationship Rules:

    1. Viewpoint:
    - The image is captured from a top-down (overhead) camera view.
    - The bottom edge of the image corresponds to the front edge of the table (closest to the camera).
    - The top edge of the image corresponds to the back edge of the table (farthest from the camera).

    To avoid confusion:
    - "In front of" means the object is **closer to the bottom edge** of the frame (i.e., nearer to the camera).
    - "Behind" means the object is **clsoser to the top edge** of the frame (i.e., farther from the camera).

    2. Surface Check:
    - If both objects are resting flat on the tabletop, they are considered to be on the same surface.
    - If one object is placed inside a container or on top of another object, they are not on the same surface.

    3. If both objects are on the tabletop:
    - Use "to the left of" if the manipulated object is horizontally to the left of the reference object.
    - Use "to the right of" if it is to the right.
    - Use "in front of" if it is closer to the front edge of the table (bottom of the image).
    - Use "behind" if it is closer to the back edge of the table (top of the image).

    4. Direction Selection Logic:
    - Determine whether the two objects are aligned more horizontally or vertically.
    - If the alignment is primarily horizontal (i.e., the x-axis difference is greater), use "to the left of" or "to the right of".
    - If the alignment is primarily vertical (i.e., the y-axis difference is greater), use "in front of" or "behind".
    - Only choose one dominant spatial direction.

    Important:
    - Always determine the direction based on the relative position between the two objects, not their absolute position in the image.
    - For example, even if both objects are near the bottom of the image, if one is clearly to the left of the other, the correct relation is "to the left of", not "in front of".

    5. If the manipulated object is not on the tabletop:
    - If it is placed inside a container, use "inside".
    - If it is placed on top of another object, use "on top of".

    6. Do not use compound or diagonal directions (e.g., "behind and to the right of"). Choose only the most dominant relation.

    7. If the spatial relationship is ambiguous or partially occluded, choose the most likely spatial relation based on the available visual evidence. Do not return "unclear".

    8. Always return a single, complete English sentence as your final answer.
    '''
    ]


    

    def forward(self, query, frame):
        conversation_history = [
            {
                "role": "system",
                "content": self.system_prompt
            },
        ]
        frames=[frame]
        original_image_paths = get_image_paths(self.video_path, frames)
        image_paths = None

        if self.flag:
            image_paths = get_keyframes_paths(original_image_paths, self.save_path)
        else:
            image_paths = get_keyframes_paths(original_image_paths, self.save_path)
            keyframes_pre(original_image_paths, image_paths)
        local_prompt=copy.deepcopy(self.prompt)
        local_prompt.append(f"The query is: {query}. The frame is provided below.")
        user_message = {
            "role": "user",
            "content":local_prompt
        }

        for idx, frame_id in enumerate(frames):
            encoded_img = encode_image(image_paths[idx])
            base64_url = f"data:image/jpeg;base64,{encoded_img}"
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
