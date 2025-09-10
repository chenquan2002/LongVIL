from transformers import Tool
import requests
import json
import base64
import http
import re
import argparse


class GenerateCode(Tool):

    name = "GenerateCode"
    description = "A tool that converts text commands into Python code."

    inputs = {
    "text_commands": {
        "description": "The text commands that the tool will convert.",
        "type": "any",
    }
    }
    output_type = "any"
    base_url = 'api.deerapi.com'

    
    def __init__(self, args):
        self.api_key = args.api_key
        self.model_name = args.model_name
        self.object_list = args.object_list
        self.headers =  {
                'Authorization': self.api_key, 
                'Content-Type': 'application/json'
                } 
        self.system_code_prompt = f'''
You are a code expert. Your task is to convert an action described in text into Python code.

Pay attention to the following guidelines:

1. You are given a description of a sequence of actions in natural language, which involves a robot performing tasks such as grabbing (picking up) and placing objects or opening and closing a drawer. Your goal is to translate this description into Python code that the robot can execute.

2. Before generating code, you must perform a structured reasoning process:

   **Step-by-step reasoning process:**
   a. Analyze the action description and extract the following:
      - The **object being picked up** (if any).
      - The **object being placed** (if any), including:
        - **Reference object** (e.g., "bowl", "drawer").
        - **Spatial preposition** (e.g., "into", "top", "right", etc.).
      - Any **open/close** actions.
   
   b. Normalize the object names:
      - You are given `object_list`:{self.object_list}, which contains all the legal object names.
      - The object names used in code must **strictly match** one of the names in `object_list`.
      - If the description includes a word like "blue box", but `object_list` has only "box", you must use `"box"`.
      - If the object in the list has color (e.g., `"orange cube"`), you must retain it.
   
   c. Normalize the spatial preposition:
      - Only use one of the following 6 valid prepositions: `["into", "top", "left", "right", "front", "behind"]`
      - Reject or replace any unsupported words like `"inside"`, `"beside"`, `"near"` etc.

3. For grabbing/picking: Use the following code pattern:
    obj_name_pos = getpos('obj_name')
    moveto(obj_name_pos)
    pick()

4. For placing: Use the following code pattern:
    obj_name_preposition = getpos('obj_name', 'preposition')
    moveto(obj_name_preposition)
    place()

    Where `obj_name` is the reference object, and `preposition` is one of the six allowed spatial relations.

5. For opening: Use `open()` to implement opening the drawer. This function requires no parameters.

6. For closing: Use `close()` to implement closing the drawer. This function requires no parameters.

7. Only use the following functions in your output: `getpos`, `moveto`, `pick`, `place`, `open`, `close`. Any other logic or function is not allowed.

8. An action may include only grabbing, only placing, or both. Opening and closing are independent actions and do not require additional object logic.

9. Your output must **only be the translated code**, enclosed by the tags `<begin_code>` and `<end_code>`. Do not include reasoning steps, commentary, or anything else.

-------------------------example1-----------------------------
**Example Input:**
object_list=['eggplant','corn','white bowl']
"A hand picks up a purple eggplant, and then places it into a bowl."

**Analysis:**
- "purple eggplant" → `eggplant` (normalized from object_list)
- "into a bowl" → reference object: `white bowl`, preposition: `into`

**Expected Output:**
<begin_code>
eggplant_pos = getpos('eggplant')
moveto(eggplant_pos)
pick()
white_bowl_into = getpos('white bowl', 'into')
moveto(white_bowl_into)
place()
<end_code>

-------------------------example2-----------------------------
**Example Input:**
object_list=['eggplant','corn','white bowl']
"A hand picks up a purple eggplant, and then places it on the top of corn."

**Analysis:**
- "purple eggplant" → `eggplant`
- "on the top of corn" → reference object: `corn`, preposition: `top`

**Expected Output:**
<begin_code>
eggplant_pos = getpos('eggplant')
moveto(eggplant_pos)
pick()
corn_top = getpos('corn', 'top')
moveto(corn_top)
place()
<end_code>

-------------------------example3-----------------------------
**Example Input:**
object_list=['eggplant','white bowl']
"A hand picks up a purple eggplant, and then places it to the right of white bowl."

**Analysis:**
- "purple eggplant" → `eggplant`
- "to the right of white bowl" → reference object: `white bowl`, preposition: `right`

**Expected Output:**
<begin_code>
eggplant_pos = getpos('eggplant')
moveto(eggplant_pos)
pick()
white_bowl_right = getpos('white bowl', 'right')
moveto(white_bowl_right)
place()
<end_code>

-------------------------example4-----------------------------
**Example Input:**
object_list=['drawer','orange cube']
"A hand opens the drawer, and then picks up an orange cube, and then places it into the drawer."

**Analysis:**
- `open()` is called directly
- "an orange cube" → `orange cube`
- "into the drawer" → reference object: `drawer`, preposition: `into`

**Expected Output:**
<begin_code>
open()
orange_cube_pos = getpos('orange cube')
moveto(orange_cube_pos)
pick()
drawer_into = getpos('drawer', 'into')
moveto(drawer_into)
place()
<end_code>
'''


    def forward(self, text_commands):  
        system_code_prompt=self.system_code_prompt
        if system_code_prompt is not None:
            conversation_history = [{
            "role": "system",
            "content": system_code_prompt
            }
            ]
        else:
            conversation_history = []
        user_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": f"The command you need to process is : {text_commands}"}
            ]
        }
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





