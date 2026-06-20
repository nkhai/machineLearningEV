"""
Base class for all EV agent tools.

Each tool represents a driving/charging mode. It knows how to:
1. Build a prompt context from the agent's current state
2. Call the LLM to generate telemetry
3. Parse and validate the response
4. Apply tool-specific overrides

Usage:
    from agent.tools.base import BaseTool
"""

import json
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI

from core.models import EVBatteryTelemetry
from prompts.loader import get_langchain_prompt

if TYPE_CHECKING:
    from agent.ev_agent import EVAgent


class BaseTool:
    """
    Base class for all EV agent tools.

    Each tool represents a driving/charging mode. It knows how to:
    1. Build a prompt context from the agent's current state
    2. Call the LLM to generate telemetry
    3. Parse and validate the response
    4. Apply tool-specific overrides

    Usage:
        tool = DrivingTool(llm)
        record = tool.execute(agent)
    """

    name: str = "base"
    description: str = "Base tool"
    scenario: str = "UNKNOWN"

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self._chain = None
        self._build_chain()

    def _build_chain(self):
        """Build the LCEL chain: prompt_template | llm."""
        prompt_template = get_langchain_prompt(self.scenario)
        self._chain = prompt_template | self.llm

    def execute(self, agent: 'EVAgent') -> EVBatteryTelemetry:
        """
        Execute this tool to generate one telemetry record.

        Args:
            agent: The EV agent providing current state

        Returns:
            EVBatteryTelemetry: A validated telemetry record
        """
        raise NotImplementedError

    @staticmethod
    def parse_response(content: str) -> str:
        """Clean LLM response: strip markdown blocks, handle NaN."""
        content = content.replace("nan", "0").replace("NaN", "0").replace("None", "0")
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        return content
