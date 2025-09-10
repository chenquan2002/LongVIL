import requests
import json
import base64
import http.client

from transformers import Tool, HfApiEngine
from transformers.agents.llm_engine import MessageRole, get_clean_message_list

gpt_role_conversions = {
    MessageRole.TOOL_RESPONSE: MessageRole.USER,
}


 
class GPTEngine(HfApiEngine):
    def __init__(self, api_key=None, model_name="gpt-4o", service_type = 'deerapi',):
        self.check_init_input(model_name, api_key,service_type)
        print("model_name",model_name)
        self.model_name = model_name
        self.api_key = api_key
        self.service_type = service_type
        if service_type =='deerapi':
            self.headers = {
                'Authorization': api_key, 
                'Content-Type': 'application/json'
                } 
            self.base_url = 'api.deerapi.com'
        if service_type =="api2d":
            self.headers = {
                'Authorization': api_key,
                'Content-Type': 'application/json'
                }
            self.base_url = 'oa.api2d.net'
        
    def check_init_input(self, model_name, api_key,service_type):
        model_name_list = ['gpt-3.5-turbo', 'gpt-4o','chatgpt-4o-latest',]
        if model_name not in model_name_list:
            raise ValueError("Wrong gpt model name:{}. The model name must in {}.".format(model_name, ", ".join(model_name_list)))  
        if api_key is None:
            raise ValueError("api key is None, please check.") 
        if service_type not in ['deerapi','api2d']:
            raise ValueError("Wrong service provider name:{}.".format(service_type))

    def __call__(self, messages,stop_sequences=[], *args, **kwargs) -> str:
        messages = get_clean_message_list(messages, role_conversions=gpt_role_conversions)
        conn = http.client.HTTPSConnection(self.base_url)
        payload = json.dumps(
        {
            "model": self.model_name,
            "messages": messages,
            "stop": stop_sequences,
            "safe_mode": False,
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

if __name__ == "__main__":

    engine = GPTEngine(api_key="sk-cAsNkBEzAEdU2sQYXOPZzA3npiUcwaMibiRnl5tYcRYWPSO7",service_type = 'deerapi',model_name="gpt-4o")
    answer = engine(
         [{"role": "user", "content": "What's the highest mountain in the world?"}]
         )
    print(answer)
    print("successful")