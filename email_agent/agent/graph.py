from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from email_agent.agent.nodes import (
    process_attachments_node,
    call_model,
    execute_tools,
    should_continue,
    decide_relevance_node,
    should_filter_or_continue,
)
from email_agent.agent.state import AgentState


def build_graph() -> CompiledStateGraph:
    """
    Uses nodes to create the agent execution graph.
    """
    workflow = StateGraph(AgentState)

    # Graph nodes
    workflow.add_node("process_attachments", process_attachments_node)
    workflow.add_node("decide_relevance", decide_relevance_node)
    workflow.add_node("call_llm", call_model)
    workflow.add_node("execute_tools", execute_tools)

    # Graph edges
    workflow.set_entry_point("process_attachments")
    workflow.add_edge("process_attachments", "decide_relevance")
    workflow.add_conditional_edges(
        "decide_relevance",
        should_filter_or_continue,
        {
            "call_model": "call_llm",  # If relevant, proceed to the main LLM call
            "filtered": END,  # If filtered (not relevant), end the flow
        },
    )
    workflow.add_conditional_edges(
        "call_llm",
        should_continue,
        {
            "tool": "execute_tools",  # If LLM wants a tool, execute it
            "final_answer": END,  # If LLM gives a reply, end the graph
        },
    )
    workflow.add_edge("execute_tools", "call_llm")

    # Compile the graph into an executable agent
    agent_executor = workflow.compile()

    # from IPython.display import Image, display
    # from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles
    # with open("langgraph_graph.png", "wb") as f:
    #     f.write(Image(agent_executor.get_graph().draw_mermaid_png()).data)

    return agent_executor


agent_executor = build_graph()
