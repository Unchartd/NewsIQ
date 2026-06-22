from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel

from agno.models.base import Model
from agno.models.response import ModelResponse
from agno.models.message import Message

@dataclass
class GatewayModel(Model):
    """Custom Agno Model adapter that intercepts and routes calls through the NewsIQ LLM Gateway."""
    stage: str = "unknown"
    story_id: str = ""
    article_id: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.name = "GatewayModel"
        self.provider = "NewsIQ Gateway"

    async def ainvoke(
        self,
        messages: List[Message],
        assistant_message: Message,
        response_format: Optional[Union[Dict[str, Any], Type[BaseModel]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        run_response: Optional[Any] = None,
        compress_tool_results: bool = False,
        retry_with_guidance: bool = False,
    ) -> ModelResponse:
        # Format Agno Messages to standard dictionary list
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg.role,
                "content": str(msg.content) if msg.content is not None else ""
            })

        # Dynamically import RequestManager to prevent circular dependencies
        from app.llm_gateway.request_manager import llm_gateway

        # Execute call via gateway
        response = await llm_gateway.execute_request(
            model=self.id,
            stage=self.stage,
            messages=formatted_messages,
            response_format=response_format,
            temperature=0.1,
            tools=tools,
            tool_choice=tool_choice,
            story_id=self.story_id,
            article_id=self.article_id
        )

        # Set token metrics on Agno message metrics
        if assistant_message.metrics:
            assistant_message.metrics.input_tokens = response.input_tokens
            assistant_message.metrics.output_tokens = response.output_tokens
            assistant_message.metrics.total_tokens = response.total_tokens

        return ModelResponse(
            role="assistant",
            content=response.content,
            parsed=response.parsed,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
        )

    def invoke(
        self,
        messages: List[Message],
        assistant_message: Message,
        response_format: Optional[Union[Dict[str, Any], Type[BaseModel]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        run_response: Optional[Any] = None,
        compress_tool_results: bool = False,
        retry_with_guidance: bool = False,
    ) -> ModelResponse:
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "role": msg.role,
                "content": str(msg.content) if msg.content is not None else ""
            })

        from app.llm_gateway.request_manager import llm_gateway

        response = llm_gateway.execute_request_sync(
            model=self.id,
            stage=self.stage,
            messages=formatted_messages,
            response_format=response_format,
            temperature=0.1,
            tools=tools,
            tool_choice=tool_choice,
            story_id=self.story_id,
            article_id=self.article_id
        )

        if assistant_message.metrics:
            assistant_message.metrics.input_tokens = response.input_tokens
            assistant_message.metrics.output_tokens = response.output_tokens
            assistant_message.metrics.total_tokens = response.total_tokens

        return ModelResponse(
            role="assistant",
            content=response.content,
            parsed=response.parsed,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
        )

    def _parse_provider_response(self, response: Any, **kwargs) -> ModelResponse:
        if isinstance(response, ModelResponse):
            return response
        return ModelResponse(content=str(response))

    def _parse_provider_response_delta(self, response: Any) -> ModelResponse:
        return ModelResponse(content=str(response))

    def invoke_stream(self, *args, **kwargs):
        raise NotImplementedError("Streaming is not supported in GatewayModel")

    async def ainvoke_stream(self, *args, **kwargs):
        raise NotImplementedError("Streaming is not supported in GatewayModel")

