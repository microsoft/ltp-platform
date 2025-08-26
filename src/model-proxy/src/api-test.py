
import openai  # pip install "openai<1.0.0"

model_endpoints = {
    "url": "http://10.150.142.182:8999",
    "key": "key1",
    "azure_api_version": "placeholder",
    "chat": {
        "azure_spec_deploy_name": ["gpt-35-turbo", "gpt-4-32k", "gpt-4"],
        "oai_spec_model": ["llama-2-13b-chat", "llama-2-70b-chat"],
    }, 
    "embedding": {
        "azure_spec_deploy_name": ["text-embedding-ada-002"],
    }
}

# test model api
def test_model_ep(ep):
    openai.api_key = ep["key"]
    openai.api_base = ep["url"]
    # test chat api
    chatapis = ep["chat"]
    ## call models in azure spec
    if "azure_spec_deploy_name" in chatapis:
        openai.api_type = "azure"
        openai.api_version = ep["azure_api_version"]
        for deploy_name in chatapis["azure_spec_deploy_name"]:
            print("="*20+deploy_name+"="*20)
            completion = openai.ChatCompletion.create(
                engine=deploy_name,
                messages=[{'role': 'user', 'content': 'Hello! What is your name?'}],
                max_tokens=5
            )
            print(completion)
    ## call models in oai spec
    if "oai_spec_model" in chatapis:
        openai.api_type = "openai"
        for model in chatapis["oai_spec_model"]:
            print("="*20+model+"="*20)
            completion = openai.ChatCompletion.create(
                model=model,
                messages=[{'role': 'user', 'content': 'Hello! What is your name?'}],
            )
            print(completion)
    #
    # test embedding api
    embeddingapis = ep["embedding"]
    ## call models in azure spec
    openai.api_type = "azure"
    openai.api_version = ep["azure_api_version"]
    for deploy_name in embeddingapis["azure_spec_deploy_name"]:
        print("="*20+deploy_name+"="*20)
        embedding = openai.Embedding.create(
            engine=deploy_name,
            input="The food was delicious and the waiter...",
        )
        print(embedding)

test_model_ep(model_endpoints)
