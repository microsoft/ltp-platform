import os
import asyncio
import json
from typing import TypedDict, Dict, List, Optional
from openai import AsyncAzureOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, OpenAIResponsesModel, trace
from langgraph.graph import StateGraph, END
import sys
from ..utils.push_frontend import push_frontend_event
from ..utils.logger import logger
# Disable debug by replacing it with a no-op function
logger.debug = lambda msg: None

# --- State Type Definition ---
class AgentFlowState(TypedDict):
    """State shared across all agents in the workflow."""
    input_prompt: str
    current_task: str
    aggregated_output: str
    last_output: str
    step_count: int


class AgentFlow:
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
        self._load_config(azure_key, azure_endpoint, azure_deployment, azure_api_version)
        self._setup_agent_config()
        self._setup_agents(agents)
    
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
                "You are an expert planning agent. Your task is to analyze the user's request "
                "and determine the exact sequence of agents needed to fulfill it, along with specific tasks for each agent. "
                f"Available agents are: {list(self.agent_dict.keys())}.\n"
                "**Your response MUST be a single JSON array of objects, where each object has 'agent' (agent name) and 'task' (specific instruction).** "
                "Use **DOUBLE quotes** for all strings. Do NOT include any other text, reasoning, or markdown (like ```json). "
                "Example: [{\"agent\": \"Calculator Agent\", \"task\": \"Calculate (8 * 9 + 50) * 100\"}, {\"agent\": \"Web Search Agent\", \"task\": \"Find a company with approximately employees in the calculated result\"}, {\"agent\": \"Story agent\", \"task\": \"Write a short math teaching story using the company name\"}]"
            ),
            model=self.chat_model_config,
            output_type=str
        )

    def parse_flow_plan(self, plan_output: str) -> List[Dict[str, str]]:
        """Parse the JSON flow plan from the agent output."""
        flow_plan_json = plan_output.strip()
        
        # Clean up potential markdown formatting (e.g., ```json ... ```)
        if flow_plan_json.startswith('```json'):
            flow_plan_json = flow_plan_json.strip('```json').strip()
        if flow_plan_json.endswith('```'):
            flow_plan_json = flow_plan_json.rstrip('```').strip()
        
        try:
            flow_plan = json.loads(flow_plan_json)
            
            if not isinstance(flow_plan, list):
                raise ValueError("Plan is not a list.")
            
            for step in flow_plan:
                if not isinstance(step, dict) or 'agent' not in step or 'task' not in step:
                    raise ValueError("Each step must be a dict with 'agent' and 'task' keys.")
                
            return flow_plan
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
    
    async def _create_agent_node(self, agent: Agent, agent_name: str):
        """Create a LangGraph node function for an agent."""
        async def node_fn(state: AgentFlowState) -> AgentFlowState:
            push_frontend_event(f'<span class="text-gray-400 italic">🔍 Step {state["step_count"]}: Executing {agent_name}</span><br/>', replace=False)
            
            # Construct input based on whether this is the first step
            if state["step_count"] == 1:
                execution_input = state["current_task"]
            else:
                execution_input = (
                    f"Previous Step Result: \n{state['aggregated_output']}\n\n"
                    f"Your Task: {state['current_task']}"
                )
            
            logger.debug(f'[execution input]\n{execution_input}')
            
            step_result = await Runner.run(agent, input=execution_input)
            output = step_result.final_output
            
            logger.debug(f"[{agent_name} Output]: \n{output}")
            
            return {
                "input_prompt": state["input_prompt"],
                "current_task": state["current_task"],
                "aggregated_output": state["aggregated_output"] + output,
                "last_output": output,
                "step_count": state["step_count"] + 1
            }
        
        return node_fn
    
    def _init_state(self, input_prompt: str, first_task: str) -> AgentFlowState:
        """Initialize the workflow state."""
        return {
            "input_prompt": input_prompt,
            "current_task": first_task,
            "aggregated_output": "",
            "last_output": "",
            "step_count": 1
        }

    async def _build_sequential_workflow(self, flow_plan: List[Dict[str, str]]):
        """Build LangGraph workflow + node functions for a linear plan."""
        workflow = StateGraph(AgentFlowState)
        node_names = []
        node_functions = []
        
        for i, step in enumerate(flow_plan):
            agent_name = step['agent']
            agent = self.agent_dict.get(agent_name)
            if not agent:
                raise ValueError(f"Agent '{agent_name}' not found.")
            
            node_name = f"step_{i}_{agent_name.replace(' ', '_')}"
            node_fn = await self._create_agent_node(agent, agent_name)
            workflow.add_node(node_name, node_fn)
            node_names.append(node_name)
            node_functions.append(node_fn)
        
        # Chain edges
        for a, b in zip(node_names, node_names[1:]):
            workflow.add_edge(a, b)
        workflow.set_entry_point(node_names[0])
        workflow.add_edge(node_names[-1], END)
        
        app = workflow.compile()
        return workflow, node_names, node_functions
    
    async def _run_sequential(self, workflow, node_names, node_functions, 
                             flow_plan: List[Dict[str, str]], state: AgentFlowState) -> AgentFlowState:
        """Run each node function manually to inject per-step task updates."""
        for i, step in enumerate(flow_plan):
            state["current_task"] = step["task"]
            state["step_count"] = i + 1
            state = await node_functions[i](state)
        return state
    
    async def _execute_flow_plan_with_langgraph(self, flow_plan: List[Dict[str, str]], input_prompt: str) -> str:
        """Orchestrate building and running the LangGraph workflow."""
        try:
            workflow, node_names, node_functions = await self._build_sequential_workflow(flow_plan)
        except ValueError as e:
            logger.error(f"Workflow build error: {e}")
            return ""
        
        state = self._init_state(input_prompt, flow_plan[0]['task'])
        final_state = await self._run_sequential(workflow, node_names, node_functions, flow_plan, state)
        return final_state["last_output"]
    
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
            plan_result = await Runner.run(
                self.flow_generator_agent,
                input=f"Analyze this request and generate the flow: {input_prompt}"
            )
            push_frontend_event(f'<span class="text-gray-400 italic">🔍 Flow Generator Output\n{plan_result.final_output}</span><br/>', replace=False)
            
            # Parse the JSON output from the Flow Generator Agent
            try:
                flow_plan = self.parse_flow_plan(plan_result.final_output)
                logger.debug(f"Generated Flow Plan: {flow_plan}")

                if not flow_plan:
                    return "No suitable workflow could be generated with the available agents. Please ensure the required agents are available for your request."
                    
            except ValueError as e:
                logger.error(f"Error parsing flow plan: {e}. Output was: {plan_result.final_output}")
                return ""
                
            # 2. Execute the Flow Plan with LangGraph
            final_output = await self._execute_flow_plan_with_langgraph(flow_plan, input_prompt)

            logger.debug(f'\n----[Dynamic Flow Complete]----')
            logger.debug(f'Final Output: \n{final_output}')
            return final_output

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

    def get_available_agents(self) -> List[str]:
        """Get a list of available agent names."""
        return list(self.agent_dict.keys())
    
    def add_agent(self, agent: Agent):
        """Add a new agent to the available agents."""
        self.agent_dict[agent.name] = agent
