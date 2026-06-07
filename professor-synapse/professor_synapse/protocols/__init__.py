"""
Protocols — pluggable specialist agent interfaces.

Each protocol is a self-contained Python module with a single public
function signature. Protocols have NO dependencies on each other
(zero coupling), only on `state.Agent` for type hints.

A protocol:
  1. Receives: agent, user_input, session_summary
  2. Returns: structured response dict
  3. Is stateless — all state lives in the session
"""

from professor_synapse.protocols.convener import handle as convener_handle
from professor_synapse.protocols.agent_template import handle as agent_template_handle


__all__ = ["convener_handle", "agent_template_handle"]
