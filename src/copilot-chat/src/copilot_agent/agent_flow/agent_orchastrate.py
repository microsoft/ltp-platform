import os
import asyncio
from typing import TypedDict, Dict, List, Optional
from openai import AsyncAzureOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, OpenAIResponsesModel, trace
from agents.exceptions import MaxTurnsExceeded
from ..utils.push_frontend import push_frontend_event
from ..utils.logger import logger
# Disable debug by replacing it with a no-op function
#logger.debug = lambda msg: None
from ..config import DATA_DIR
from .agent_tool import websearch_agent, story_agent, calculator_agent, python_coder_agent, plotter_agent, translation_agent

# --- State Type Definition ---
class AgentFlowState(TypedDict):
    """State shared across all agents in the workflow."""
    input_prompt: str
    current_task: str
    aggregated_output: str
    last_output: str
    step_count: int
    all_outputs: List[Dict[str, str]]  # Track all agent outputs with metadata


class AgentOrchestrate:
    """
    A class that orchestrates the execution of AI agents in a dynamic workflow.
    
    This orchestrator can analyze user requests, generate execution plans, 
    and coordinate multiple AI agents to fulfill complex tasks.
    """
    
    def __init__(self, 
                 agents: List[Agent],
                 azure_key: Optional[str] = None,
                 azure_endpoint: Optional[str] = None, 
                 azure_deployment: Optional[str] = None,
                 azure_api_version: Optional[str] = None):
        """
        Initialize the Analysis Orchestrator.
        
        Args:
            agents: List of Agent instances to be available for orchestration
            azure_key: Azure OpenAI API key (defaults to env var)
            azure_endpoint: Azure OpenAI endpoint (defaults to env var)
            azure_deployment: Azure OpenAI deployment name (defaults to env var)
            azure_api_version: API version to use
        """
        max_turn = os.environ.get("AZURE_OPENAI_AGENTSDK_MAX_TURNS", 50)
        if max_turn.isdigit():
            self.max_turns = int(max_turn)
        else:
            self.max_turns = 50
        self._load_config(azure_key, azure_endpoint, azure_deployment, azure_api_version)
        self._setup_agent_config()
        self._setup_agent_as_tools()
        self._setup_agents(agents)
        self.data_dir = DATA_DIR
    
    def _load_config(self, azure_key: Optional[str], azure_endpoint: Optional[str], 
                    azure_deployment: Optional[str], azure_api_version: str):
        """Load configuration from environment variables or parameters."""
        self.azure_key = azure_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = azure_deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.azure_api_version = azure_api_version or os.getenv("AZURE_OPENAI_API_VERSION")

        if not all([self.azure_key, self.azure_endpoint, self.azure_deployment, self.azure_api_version]):
            raise ValueError(
                "Missing required Azure OpenAI configuration. "
                "Please provide azure_key, azure_endpoint, and azure_deployment "
                "or set the corresponding environment variables."
            )
    
    def _setup_agent_config(self):
        """Initialize the Azure OpenAI client."""
        self.openai_client = AsyncAzureOpenAI(
            api_key=self.azure_key,
            api_version=self.azure_api_version,
            azure_endpoint=self.azure_endpoint,
            azure_deployment=self.azure_deployment
        )

        """Initialize and configure all agents."""
        # Model configurations
        self.chat_model_config = OpenAIChatCompletionsModel(
            model=self.azure_deployment,
            openai_client=self.openai_client
        )
        
        self.responsive_model_config = OpenAIResponsesModel(
            model=self.azure_deployment,
            openai_client=self.openai_client
        )

    def _setup_agent_as_tools(self):
        self.agent_as_tools = [
            websearch_agent.as_tool(
                tool_name="web_search",
                tool_description="Useful for searching the web for up-to-date information.",
                is_enabled=True,
            ),
            story_agent.as_tool(
                tool_name="story_generation",
                tool_description="Useful for generating creative stories based on user prompts.",
                is_enabled=True,
            ),
            calculator_agent.as_tool(
                tool_name="calculator",
                tool_description="Useful for performing mathematical calculations.",
                is_enabled=True,
            ),
            python_coder_agent.as_tool(
                tool_name="python_coder",
                tool_description="Useful for writing and debugging Python code.",
                is_enabled=True,
            ),
            plotter_agent.as_tool(
                tool_name="data_plotter",
                tool_description="Useful for creating data visualizations and plots.",
                is_enabled=True,
            ),
            translation_agent.as_tool(
                tool_name="language_translation",
                tool_description="Useful for translating text between different languages.",
                is_enabled=True,
            ),
        ]

    def _setup_agents(self, agents: List[Agent]):
        """Initialize and configure all agents.
        
        Args:
            agents: List of Agent instances to be available for orchestration
        """
        # Create agent dictionary from provided agents
        self.agent_dict: Dict[str, Agent] = {agent.name: agent for agent in agents}
        
        # Flow generator agent
        self.flow_generator_agent = Agent(
            name="FlowGeneratorAgent",
            instructions=(
                "You are a multilingual assistant. You use the tools given to you to respond to users. "
                "You must call ALL available tools to provide responses in different languages. "
                "You never respond in languages yourself, you always use the provided tools."
            ),
            model=self.chat_model_config,
            tools=self.agent_as_tools,
            output_type=str
        )

    def _convert_file_paths_to_markdown(self, text: str) -> str:
        """Convert file paths to markdown image syntax."""
        import re
        import os
        
        # Pattern to match file paths ending with image extensions
        image_extensions = r'\.(png|jpg|jpeg|gif|svg|webp)'
        
        # Pattern 1: Match absolute paths containing data/img/
        pattern1 = rf'([^\s\)]*data/img/[^\s\)]*{image_extensions})'
        
        # Pattern 2: Match paths that start with ./ and contain data/img/
        pattern2 = rf'(\./[^\s\)]*data/img/[^\s\)]*{image_extensions})'
        
        def replace_with_markdown(match):
            file_path = match.group(1)
            # Extract just the filename from the path
            filename = file_path.split('/')[-1]
            
            # Check if we're in local development mode
            agent_mode = os.getenv('AGENT_MODE', '').lower()
            agent_host = os.getenv('AGENT_HOST', '127.0.0.1')
            agent_port = os.getenv('AGENT_PORT', '60000')
            
            if agent_mode == 'local':
                # Use absolute URL for local development to avoid frontend/backend port conflicts
                web_path = f'http://{agent_host}:{agent_port}/copilot/static/img/{filename}'
            else:
                # Use relative path for production
                web_path = f'/copilot/static/img/{filename}'
            
            return f'![Generated Plot]({web_path})'
        
        # Apply both patterns
        text = re.sub(pattern1, replace_with_markdown, text, flags=re.IGNORECASE)
        text = re.sub(pattern2, replace_with_markdown, text, flags=re.IGNORECASE)
        
        return text

    async def execute_flow(self, input_prompt: str) -> str:
        """
        Execute a dynamic flow based on the input prompt.
        
        This is the main public method that:
        1. Analyzes the input prompt
        2. Generates an execution plan
        3. Orchestrates the execution of multiple agents
        4. Returns the final result
        
        Args:
            input_prompt: The user's request to fulfill
            
        Returns:
            The final output from the orchestrated agent workflow
        """
        logger.debug(f'\n----[Analyzer: Runtime Flow Generation with LangGraph]----')
        logger.debug(f'[input]\n{input_prompt}')
        
        with trace("DynamicFlow"):
            # 1. Generate the Flow Plan (The sequence of agents)
            push_frontend_event(f'<span class="text-gray-400 italic">🔍 Step 0: Generating Execution Plan...</span><br/>', replace=False)
            
            try:
                plan_result = await Runner.run(
                    self.flow_generator_agent,
                    input=f"Analyze this request and generate the flow: {input_prompt}",
                    max_turns=self.max_turns
                )
                plan_result_output = plan_result.final_output
                
            except MaxTurnsExceeded:
                # Use first available agent as fallback
                available_agents = list(self.agent_dict.keys())
                plan_result_output = f'[{{"agent": "{available_agents[0]}", "task": "{input_prompt}", "needs_summary": false}}]' if available_agents else "[]"
                push_frontend_event(f'<span class="text-gray-400 italic">⚠️ Flow generation exceeded max turns. Using fallback plan: {plan_result_output}</span><br/>', replace=False)


            logger.debug(f'\n----[Dynamic Flow Complete]----')
            logger.debug(f'Final Output: \n{plan_result_output}')
            final_output_converted = self._convert_file_paths_to_markdown(plan_result_output)
            return final_output_converted

    def async_execute_flow(self, question: str, context_message: list | None) -> str:
        """Synchronous wrapper to run the async execute_flow method."""
        question_prompt = f'[user question]\n {question} \n\n'
        if context_message:
            context_prompt = f'[context message]\n {" ".join(context_message)} \n\n'
        else:
            context_prompt = ''
        input_prompt = (question_prompt + context_prompt)
        logger.info(f'[async_execute_flow] input_prompt: {input_prompt}')
        answer = asyncio.run(self.execute_flow(input_prompt))
        push_frontend_event(f'<span class="text-gray-400 italic">✅ Analysis result</span><br/>', replace=False)
        push_frontend_event(f'<span class="text-black">{answer}</span><br/>', replace=False)
        return answer
