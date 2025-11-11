import os
import asyncio
import json
import subprocess
import tempfile
import sys
import uuid
from typing import TypedDict, Annotated
from openai import AsyncAzureOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, OpenAIResponsesModel, function_tool
from ..config import DATA_DIR


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
def power_tool(base: float, exponent: float) -> float:
    """Raise base to the power of exponent and return the result."""
    print(f'[tool][power]\nbase: {base}, exponent: {exponent}')
    return base ** exponent

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

@function_tool
def uuid_v4_generator() -> str:
    """Generate a UUID v4 string."""
    generated_uuid = str(uuid.uuid4())
    print(f'[tool][uuid_v4_generator]\nGenerated UUID: {generated_uuid}')
    return generated_uuid

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
    tools=[adder_tool, multiplier_tool, power_tool],
    output_type=str
)

python_coder_agent = Agent(
    name="Python Programming and Development Agent",
    instructions="""You are a Python programming expert that can write, execute, and analyze Python code for general programming tasks.
    
    When asked to solve a problem or write code:
    1. Write clean, well-documented Python code
    2. Use the python_code_executor tool to run your code
    3. Analyze the output and provide explanations
    4. If there are errors, debug and fix them by writing corrected code
    5. Always test your solutions to ensure they work correctly
    
    You handle various Python tasks including:
    - Data processing and manipulation (without visualization)
    - Mathematical calculations and algorithms
    - Algorithm implementations and data structures
    - File operations and I/O handling
    - String processing and text manipulation
    - API integrations and web scraping
    - Database operations
    - Unit testing and debugging
    - System automation and scripting
    - General Python programming tasks
    
    IMPORTANT: You do NOT handle plotting, charting, or data visualization tasks. 
    If a user asks for plots, charts, graphs, or any visual output, redirect them to use the specialized "Data Visualization and Plotting Agent" instead.
    
    Always provide clear explanations of what your code does and what the results mean.""",
    model=chat_model_config,
    tools=[python_code_executor],
    output_type=str
)

plotter_agent = Agent(
    name="Data Visualization and Plotting Agent",
    instructions=f"""You are a specialized plotting agent that creates data visualizations and saves them as PNG files for server backend operations.

    Your workflow should always be:
    1. First, use the uuid_v4_generator tool to generate a unique filename
    2. Write Python code to create the plot/chart using matplotlib, seaborn, or other plotting libraries
    3. In your Python code, save the plot as a PNG file to: {DATA_DIR}/img/{{uuid}}.png
    4. Use python_code_executor to run the plotting code
    5. Return only the full file path as a string: {DATA_DIR}/img/{{uuid}}.png
    
    CRITICAL SERVER BACKEND REQUIREMENTS:
    - NEVER use plt.show() - this is a server environment without display
    - ALWAYS use plt.close() or plt.clf() after saving to free memory
    - Use matplotlib's 'Agg' backend for headless operation: plt.switch_backend('Agg')
    - Set matplotlib to non-interactive mode at the start of your code
    
    Code structure template:
    ```python
    import matplotlib
    matplotlib.use('Agg')  # Set backend for server environment
    import matplotlib.pyplot as plt
    plt.ioff()  # Turn off interactive mode
    
    # Your plotting code here
    
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()  # Always close to free memory
    ```
    
    Important guidelines:
    - Always generate a UUID first before writing any plotting code
    - Save plots with high DPI (e.g., dpi=300) for good quality
    - Use bbox_inches='tight' instead of plt.tight_layout() for better server performance
    - Handle any required data generation or processing within your Python code
    - Return ONLY the file path, nothing else
    - Optimize for server performance and memory management
    
    You specialize in creating:
    - Statistical plots and data visualizations
    - Charts, graphs, and diagrams
    - Scientific plots and mathematical visualizations
    - Business intelligence dashboards and reports
    - Data analysis visualizations
    - Any plotting, charting, or visualization request
    
    Example workflow:
    1. Generate UUID: "abc123-def456-..."
    2. Create Python code that saves to: {DATA_DIR}/img/abc123-def456-....png
    3. Execute the code
    4. Return: "{DATA_DIR}/img/abc123-def456-....png" """,
    model=chat_model_config,
    tools=[python_code_executor, uuid_v4_generator],
    output_type=str
)

translation_agent = Agent(
    name="Translation Agent",
    instructions="""You are a professional language translator with expertise in multiple languages.

    Your capabilities include:
    - Translating text between any two languages
    - Detecting the source language automatically when not specified
    - Providing accurate, contextually appropriate translations
    - Handling various text types: formal, informal, technical, literary, etc.
    - Explaining translation choices when requested
    - Providing alternative translations when multiple interpretations are possible

    When translating:
    1. Always preserve the original meaning and tone
    2. Consider cultural context and idiomatic expressions
    3. Maintain formatting (if any) from the original text
    4. If the source language is ambiguous, ask for clarification
    5. For technical or specialized terms, provide the most accurate translation
    6. If multiple translations are valid, mention alternatives

    Supported languages include but are not limited to:
    - English, Chinese (Simplified/Traditional), Japanese, Korean
    - Spanish, French, German, Italian, Portuguese, Russian
    - Arabic, Hindi, Thai, Vietnamese, Indonesian
    - And many others

    Example usage:
    - "Translate 'Hello, how are you?' to Spanish"
    - "Translate this Chinese text to English: 你好吗？"
    - "What does 'Bonjour' mean in English?"
    
    Always provide clear, accurate translations with proper context.""",
    model=chat_model_config,
    output_type=str
)

agents_list = [websearch_agent, story_agent, calculator_agent, python_coder_agent, plotter_agent, translation_agent]