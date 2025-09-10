from transformers import Tool
import json
import os

class Savetext(Tool):

    name = "Savetext"
    description = "A tool that saves list-type results."

    inputs = {
    "savepath": {
    "description": "The path where the results will be saved.",
    "type": "string",
    } ,
    "result": {
    "description": "The results to be saved. ",
    "type": "any"
    }
    }
    output_type = "string"

    def __init__(self,resultname):
        super().__init__()
        self.resultname = resultname


    def forward(self,savepath:str,result):
        save_path = os.path.join(savepath,f'Result.json')
        if self.resultname=='Plan':
            try:
                if not isinstance(result,list): 
                    raise TypeError("The result should be a list of dictionaries.")
                data={"action_sequences":result}
                with open(save_path, 'w') as f:
                    json.dump(data, f, indent=4)
                return "Save Plan successfully."
            except Exception as e:
                return f"Failed to save results to {save_path}. Error: {str(e)}"
            
            except TypeError as e:
                return f"The result should be a list of dictionaries. Error: {str(e)}"
       
        else:
            try:
                if not isinstance(result, list):
                    raise TypeError("The result should be a list of dictionaries.")
                

                if os.path.exists(save_path):
                    with open(save_path, 'r') as f:
                        existing_data = json.load(f)
                    if "code" in existing_data and isinstance(existing_data["code"], list):
                        existing_data["code"].extend(result)
                    else:
                        existing_data["code"] = result
                else:
                    existing_data = {"code": result}

             
                with open(save_path, 'w') as f:
                    json.dump(existing_data, f, indent=4)
                return "Appended code successfully."

            except Exception as e:
                return f"Failed to save results to {save_path}. Error: {str(e)}"

            except TypeError as e:
                return f"The result should be a list of dictionaries. Error: {str(e)}"

        

    

