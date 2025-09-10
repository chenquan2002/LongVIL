from LongVIL.engines.gpt_engine import GPTEngine

def get_llm_engine(args):
    if args.engine_type == "gpt":
        if args.api_key is None:
            raise ValueError("GPT api key not set.")
        return GPTEngine(api_key=args.api_key, model_name=args.llm_model_name)
    else:
        raise ValueError(f"Unknown LLM engine {args.engine_type}")
