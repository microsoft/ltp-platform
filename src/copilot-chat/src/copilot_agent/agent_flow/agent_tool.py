import os
import asyncio
import json
from typing import TypedDict, Annotated
from openai import AsyncAzureOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, OpenAIResponsesModel, function_tool


# --- 1. Configuration Variables ---
try:
    AZURE_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-03-01-preview") 
    
    if not all([AZURE_KEY, AZURE_ENDPOINT, AZURE_DEPLOYMENT]):
        raise ValueError("Missing required Azure OpenAI environment variables.")

except ValueError as e:
    print(f"Configuration Error: {e}")
    print("Please check your .env file and ensure AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT are set.")
    exit()

# --- 2. Initialize the Azure OpenAI Client ---
# Use the AsyncAzureOpenAI client from the 'openai' library
# Note: The 'model' parameter in the chat_model_config will correspond to the 
# AZURE_DEPLOYMENT name, not the base model name (e.g., gpt-4o).
openai_client = AsyncAzureOpenAI(
    api_key=AZURE_KEY,
    api_version=AZURE_API_VERSION,
    azure_endpoint=AZURE_ENDPOINT,
    azure_deployment=AZURE_DEPLOYMENT # This is technically redundant here, but good practice
)

# --- 3. Define the Agent ---

# Define the model configuration, explicitly passing the Azure client
chat_model_config = OpenAIChatCompletionsModel(
    # The 'model' parameter must be your Azure Deployment Name
    model=AZURE_DEPLOYMENT, 
    openai_client=openai_client 
)

# Define the model configuration, explicitly passing the Azure client
responsive_model_config = OpenAIResponsesModel(
    # The 'model' parameter must be your Azure Deployment Name
    model=AZURE_DEPLOYMENT, 
    openai_client=openai_client 
)

# --- 4. Create the Agent instance ---
@function_tool
def adder_tool(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    print(f'[tool][adder]\na: {a}, b: {b}')
    return a + b

@function_tool
def multiplier_tool(a: float, b: float) -> float:
    """Add two integers and return the sum."""
    print(f'[tool][multiplier]\na: {a}, b: {b}')
    return a * b

websearch_agent = Agent(
    name="Web Search Agent",
    instructions="You are a fake web search agent. Provide a fake search result to the query.",
    model=chat_model_config,
    output_type=str
)

story_agent = Agent(
    name="Story agent",
    instructions="You are a creative storyteller, the output should be concise.",
    model=chat_model_config
)

calculator_agent = Agent(
    name="Calculator Agent",
    instructions="You are a accurate calculator, you should always use tools to calculate, and you should always output the processes taken to arrive at the final result.",
    model=chat_model_config,
    tools=[adder_tool, multiplier_tool],
    output_type=str
)