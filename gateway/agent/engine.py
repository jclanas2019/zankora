"""Abstract interface for agent engines."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from gateway.domain.models import AgentRun


class AgentEngine(ABC):
    """Abstract base class for agent execution engines.
    
    Engines orchestrate agent runs but must respect the single-authority principle:
    - The Gateway is the only component that mutates state
    - Tools must be executed via ToolRegistry + PolicyEngine
    - All side effects go through the EventBus
    """

    @abstractmethod
    async def run(self, run: AgentRun, context_messages: list[dict[str, str]]) -> AgentRun:
        """
        Execute an agent run.
        
        Args:
            run: The agent run to execute (with run_id, chat_id, etc.)
            context_messages: Context messages (history + user prompt)
            
        Returns:
            Updated AgentRun with status, output_text, summary, etc.
            
        The engine must:
        - Emit progress events via EventBus
        - Execute tools via ToolRegistry respecting PolicyEngine
        - Handle approvals for write tools
        - Respect max_steps and timeout limits
        - Update run.status, run.output_text, run.summary before returning
        - NOT persist run (Gateway does this)
        """
        pass

    @abstractmethod
    def grant_approval(self, run_id: str) -> bool:
        """
        Grant approval for a pending tool execution.
        
        Args:
            run_id: The run ID waiting for approval
            
        Returns:
            True if approval was granted, False if no pending approval found
        """
        pass
