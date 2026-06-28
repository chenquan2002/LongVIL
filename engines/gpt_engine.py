from transformers import Tool, HfApiEngine
from transformers.agents.llm_engine import MessageRole, get_clean_message_list
from LongVIL.tools.api_utils import build_headers, get_api_base_url, log_token_usage, request_chat_completion

gpt_role_conversions = {
    MessageRole.TOOL_RESPONSE: MessageRole.USER,
}


 
class GPTEngine(HfApiEngine):
    def __init__(self, api_key=None, model_name="gpt-4o", base_url=None):
        self.check_init_input(api_key)
        print("model_name",model_name)
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url or get_api_base_url()
        self.headers = build_headers(api_key)
        
    def check_init_input(self, api_key):
        if api_key is None:
            raise ValueError("api key is None, please check.") 

    def __call__(self, messages,stop_sequences=[], *args, **kwargs) -> str:
        messages = get_clean_message_list(messages, role_conversions=gpt_role_conversions)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stop": stop_sequences,
            "safe_mode": False,
        }
        response_data = request_chat_completion(self.base_url, self.headers, payload)
        log_token_usage("engine", response_data)
        if 'choices' in response_data and len(response_data['choices']) > 0:
            assistant_message = response_data['choices'][0]['message']
            
            return assistant_message['content']
        else:
            print("there's wrong with the gpt output, the returned messages are: ", response_data)
            return "No available response."

if __name__ == "__main__":

    engine = GPTEngine(api_key="YOUR_API_KEY", base_url="https://your_baseurl/v1/chat/completions", model_name="gpt-4o")
    answer = engine(
         [{"role": "user", "content": "What's the highest mountain in the world?"}]
         )
    print(answer)
    print("successful")
