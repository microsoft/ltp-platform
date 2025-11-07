import os
import asyncio
import json
import subprocess
import tempfile
import sys
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

@function_tool
def python_code_executor(code: str) -> str:
    """
    Execute Python code and return the result as a string.
    
    Args:
        code: The Python code to execute
        
    Returns:
        String containing the output of the executed code, including stdout and stderr
    """
    print(f'[tool][python_code_executor]\nExecuting code:\n{code}')
    
    try:
        # Create a temporary file to store the Python code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_file.write(code)
            temp_file_path = temp_file.name
        
        # Execute the Python code using subprocess
        result = subprocess.run(
            [sys.executable, temp_file_path],
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout for safety
        )
        
        # Clean up the temporary file
        os.unlink(temp_file_path)
        
        # Combine stdout and stderr
        output = ""
        if result.stdout:
            output += f"Output:\n{result.stdout}"
        if result.stderr:
            if output:
                output += "\n"
            output += f"Errors:\n{result.stderr}"
        
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"
        
        return output if output else "Code executed successfully with no output."
        
    except subprocess.TimeoutExpired:
        # Clean up the temporary file in case of timeout
        if 'temp_file_path' in locals():
            try:
                os.unlink(temp_file_path)
            except:
                pass
        return "Error: Code execution timed out after 30 seconds."
    
    except Exception as e:
        # Clean up the temporary file in case of other errors
        if 'temp_file_path' in locals():
            try:
                os.unlink(temp_file_path)
            except:
                pass
        return f"Error executing code: {str(e)}"

websearch_agent = Agent(
    name="Web Search Agent",
    instructions="You are a fake web search agent. Provide a fake search result to the query.",
    model=chat_model_config,
    output_type=str
)

story_agent = Agent(
    name="Story agent",
    instructions="You are a creative storyteller, the output should be concise. Use markdown format where appropriate.",
    model=chat_model_config
)

calculator_agent = Agent(
    name="Calculator Agent",
    instructions="You are a accurate calculator, you should always use tools to calculate, and you should always output the processes taken to arrive at the final result.",
    model=chat_model_config,
    tools=[adder_tool, multiplier_tool],
    output_type=str
)

python_coder_agent = Agent(
    name="Python Coder Agent",
    instructions="""You are a Python programming expert that can write, execute, and analyze Python code.
    
    When asked to solve a problem or write code:
    1. Write clean, well-documented Python code
    2. Use the python_code_executor tool to run your code
    3. Analyze the output and provide explanations
    4. If there are errors, debug and fix them by writing corrected code
    5. Always test your solutions to ensure they work correctly
    
    You can handle various Python tasks including:
    - Data analysis and manipulation
    - Mathematical calculations
    - Algorithm implementations
    - File operations
    - String processing
    - And any other Python programming tasks
    
    Always provide clear explanations of what your code does and what the results mean.""",
    model=chat_model_config,
    tools=[python_code_executor],
    output_type=str
)

agents_list = [websearch_agent, story_agent, calculator_agent, python_coder_agent]