import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from openai import OpenAI

from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tool_registry import tool_registry

logger = logging.getLogger(__name__)

class AgentMessageResult:
    def __init__(self, text_response: str, document_paths: List[str] = None):
        self.text_response = text_response
        self.document_paths = document_paths or []

class SupermarketOpsAgent:
    """
    Autonomous ReAct Agent for Supermarket Operations.
    Implements tool calling, multi-turn reasoning, ambiguity handling, and document attachments.
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL
        
        # Initialize OpenAI compatible client
        api_key = settings.LLM_API_KEY or "dummy_key_for_local_testing"
        base_url = settings.LLM_BASE_URL if settings.LLM_BASE_URL else None
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

    def process_message(
        self,
        db: Session,
        user_message: str,
        chat_history: List[Dict[str, Any]] = None
    ) -> AgentMessageResult:
        """
        Process a user's natural language request through the ReAct agent control loop.
        Returns text response and any generated file document paths (PDF/PPTX).
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Append chat history if provided
        if chat_history:
            messages.extend(chat_history)
            
        messages.append({"role": "user", "content": user_message})

        document_paths = []
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Agent Loop Iteration {iteration}...")

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tool_registry.schemas if tool_registry.schemas else None,
                    tool_choice="auto"
                )
            except Exception as e:
                logger.error(f"LLM API Call failed: {e}")
                # Fallback response if API key is not configured or network error occurs
                return AgentMessageResult(
                    text_response=f"⚠️ LLM API call error: {str(e)}. Please check your API key configuration in .env.",
                    document_paths=[]
                )

            choice = response.choices[0]
            msg = choice.message
            
            # Convert message to dict format for trajectory
            msg_dict = {"role": "assistant"}
            if msg.content:
                msg_dict["content"] = msg.content
            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in msg.tool_calls
                ]

            messages.append(msg_dict)

            # Check if LLM decided to call tools
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                        
                    logger.info(f"Tool Call: {fn_name}({args})")
                    
                    tool_result = tool_registry.execute_tool(fn_name, args, db)
                    logger.info(f"Tool Result: {tool_result}")

                    # Check for generated file document paths in tool result
                    if isinstance(tool_result, dict):
                        if "pdf_file_path" in tool_result and tool_result["pdf_file_path"]:
                            document_paths.append(tool_result["pdf_file_path"])
                        if "pptx_file_path" in tool_result and tool_result["pptx_file_path"]:
                            document_paths.append(tool_result["pptx_file_path"])
                        if "bill" in tool_result and isinstance(tool_result["bill"], dict) and "pdf_file_path" in tool_result["bill"]:
                            document_paths.append(tool_result["bill"]["pdf_file_path"])

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": fn_name,
                        "content": json.dumps(tool_result)
                    })
                # Continue loop to allow LLM to reason over tool results
                continue
            else:
                # LLM finished reasoning and returned final text response
                final_text = msg.content or "Operation processed."
                return AgentMessageResult(
                    text_response=final_text,
                    document_paths=document_paths
                )

        return AgentMessageResult(
            text_response="Task execution reached maximum iteration limit.",
            document_paths=document_paths
        )

# Module instance
agent_instance = SupermarketOpsAgent()
