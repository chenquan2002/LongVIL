import requests
import json
import base64
import http
import re
import argparse
from transformers import Tool
class CodeVerify(Tool):
    name = "CodeVerify"
    description = "A tool that verifies and corrects if action list corresponds to Python code."

    inputs = {
        "action_list": {
            "description": "The list of actions that should be verified.",
            "type": "string",
        },
        "python_code": {
            "description": "The Python code that should be verified against the action list.",
            "type": "string",
        }
    }
    output_type = "string"
    base_url = 'api.deerapi.com'

    def __init__(self, args):
        self.api_key = args.api_key
        self.model_name = args.model_name
        self.object_list=args.object_list
        self.headers = {
            'Authorization': self.api_key, 
            'Content-Type': 'application/json'
        } 
        self.system_code_prompt = f"""
You are a Python code expert. Your task is to verify whether the provided list of actions is correctly implemented in the given Python code.

## 🎯 Your Objectives:
You must follow these steps strictly:

### Step 1: Action Understanding
- Each action is a sentence (e.g., "Pick up the banana and place it to the left of the bowl.")
- You need to extract:
  - The object to be picked up
  - The object to be placed near (if any)
  - The spatial relation used (preposition like 'left', 'into', etc.)
- Extract the **full object names from the action**, including any color or descriptive modifiers (e.g., "blue box", "white bowl").
- You must then validate that these full object names **exactly match one of the entries in the provided `object_list`:{self.object_list}**.
- If an object mentioned in the action is not present in `object_list`, you must flag it as invalid.
- If the object is in the `object_list`, but now has a different description, you need to modify it to match the description in the object_list (for example, the word you are using now is `blue box`, and the word in the object_list is `box`, so you need to adjust it to `box` ).
- Format your understanding like this:
  [Action Understanding]: Picked object = 'box'; Placement = 'into the white bowl'

### Step 2: Code Analysis
- For each action, analyze whether the corresponding Python code correctly reflects the logic of that action.
- You are given an `object_list`:{self.object_list}, which defines the **only valid object names** you may use.
- The object names used in the code must:
  - Match the object mentioned in the action
  - And **exactly match** the spelling and format of an entry in `object_list` (e.g., if `object_list` has "blue box", then `getpos('box')` is invalid)
  - Be consistent with the action's intent and reference

#### For "Pick and Place" actions:
The expected code logic should follow this order:
1. Get the position of the object to pick: `getpos('<object>')`
2. Move to that position: `moveto(...)`
3. Pick the object: `pick()`
4. Get the target placement position: `getpos('<reference object>', '<preposition>')`
5. Move to that location: `moveto(...)`
6. Place the object: `place()`

#### For "Open"/"Close" actions:
- Just check if `open()` or `close()` exists appropriately.

### Step 3: Identify Issues (if any)
If the code deviates from the expected pattern, identify the type of error. Common types of mismatches include:
- Missing operations (e.g., `pick()` not present, or `moveto(...)` missing before pick)
- Wrong order of operations (e.g., picking before moving)
- Wrong object referenced (e.g., placing behind the wrong object)
- Wrong preposition used (e.g., using 'top' instead of 'left')
- Logical placement mismatch (e.g., object placed next to the wrong container)
- Using unsupported prepositions (e.g., 'on' instead of 'top', 'in' instead of 'into')
- ❗ Using an object name in code that is not in `object_list`

Output a structured judgment like:
- [Code Analysis]: ✅ Code correctly implements this action.
- [Code Analysis]: ❌ Code has an error. [Describe what is wrong, e.g., "Missing pick() before placing", or "Used 'left' instead of 'into'"]

### Step 4: Correction (if needed)
If the code is incorrect:
- Explain what is wrong and why it doesn't match the described action.
- Output the **corrected code only**, wrapped in:
  <begin_code>
  ... corrected code ...
  <end_code>

### ⚠️ Constraints:
- Only these spatial prepositions are allowed: 'left', 'right', 'behind', 'front', 'top', 'into'
- Do not invent or accept any other prepositions (e.g., 'on', 'in', 'beside')
- The Python code must use object names that exactly match the entries in the provided `object_list`
- If the provided code is already correct, do not modify it—just state that it is correct.

========================================================
Below are a few examples to guide your formatting and logic:
========================================================

------------------- Example 1 -------------------
**Input:**
object_list = ['banana', 'bowl', 'drawer', 'chili']

action_list = [
    "Pick up the banana and place it to the left of the bowl.",
    "Open the drawer.",
    "Pick up the chili and place the chili into the drawer."
]

python_code = [
'''
banana_pos = getpos('banana')
moveto(banana_pos)
pick()
bowl_left = getpos('bowl', 'left')
moveto(bowl_left)
place()''',
'''open()''',
'''chili_pos = getpos('chili')
moveto(chili_pos)
pick()
drawer_left = getpos('drawer', 'left')
moveto(drawer_left)
place()
'''
]

**Expected Output:**
[Action Understanding]: Picked object = 'banana'; Placement = 'left of the bowl'  
[Code Analysis]: ✅ Code correctly implements this action.

[Action Understanding]: Action = 'Open the drawer'  
[Code Analysis]: ✅ Code contains `open()`

[Action Understanding]: Picked object = 'chili'; Placement = 'into the drawer'  
[Code Analysis]: ❌ Used 'left' instead of 'into' for the drawer. This does not match the action instruction.

<begin_code>
banana_pos = getpos('banana')
moveto(banana_pos)
pick()
bowl_left = getpos('bowl', 'left')
moveto(bowl_left)
place()
open()
chili_pos = getpos('chili')
moveto(chili_pos)
pick()
drawer_into = getpos('drawer', 'into')
moveto(drawer_into)
place()
<end_code>

------------------- Example 2 -------------------
**Input:**
object_list = ['banana', 'bowl']

action_list = [
    "Pick up the banana and place it to the left of the bowl."
]

python_code = [
'''
banana_pos = getpos('banana')
moveto(banana_pos)
place()
bowl_top = getpos('bowl', 'top')
moveto(bowl_top)
place()
'''
]

**Expected Output:**
[Action Understanding]: Picked object = 'banana'; Placement = 'left of the bowl'  
[Code Analysis]: ❌ Missing `pick()` before placement; used 'top' instead of 'left' — both are incorrect.

<begin_code>
banana_pos = getpos('banana')
moveto(banana_pos)
pick()
bowl_left = getpos('bowl', 'left')
moveto(bowl_left)
place()
<end_code>

------------------- Example 3 -------------------
**Input:**
object_list = ['carrot', 'white bowl']

action_list = [
    "Pick up the carrot and place it behind the white bowl."
]

python_code = [
'''
carrot_pos = getpos('carrot')
moveto(carrot_pos)
pick()
banana_behind = getpos('banana', 'behind')
moveto(banana_behind)
place()
'''
]

**Expected Output:**
[Action Understanding]: Picked object = 'carrot'; Placement = 'behind white bowl'  
[Code Analysis]: ❌ Wrong placement reference — used 'banana' instead of 'white bowl'; also, 'banana' is not in object_list.

<begin_code>
carrot_pos = getpos('carrot')
moveto(carrot_pos)
pick()
bowl_behind = getpos('white bowl', 'behind')
moveto(bowl_behind)
place()
<end_code>
"""


        
    def forward(self, action_list, python_code):
        system_code_prompt = self.system_code_prompt
        conversation_history = [{
            "role": "system",
            "content": system_code_prompt
        }]
        
      
        user_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": f"The actions are: {action_list}. The Python code is: {python_code}"}
            ]
        }

        conversation_history.append(user_message)

        conn = http.client.HTTPSConnection(self.base_url)

        payload = json.dumps({
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
            print("error", response_data)
            return "error"




