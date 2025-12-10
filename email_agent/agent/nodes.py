from typing import Any, Dict, Literal, List
from langchain_core.messages import ToolMessage

from langsmith import traceable
from email_agent.agent.state import AgentState, RelevanceAssessment
from email_agent.config import CFG
from langchain_core.prompts import PromptTemplate
from email_agent.services.attachments import process_attachments
from email_agent.utils.logger import logger
from langchain_core.messages import HumanMessage, AIMessage
from email_agent.services.llm import llm

from email_agent.tools.vector_search import knowledge_base_search


TOOLS = [knowledge_base_search]
LLM_WITH_TOOLS = llm.bind_tools(TOOLS)
RELEVENCE_LLM = llm.with_structured_output(RelevanceAssessment)

# Load initial Jinja2-templated prompt
with open(CFG.sys_prompt_path, "r", encoding="utf-8") as file:
    SYSTEM_PROMPT = PromptTemplate(
        input_variables=[
            "sender",
            "subject",
            "date",
            "body",
            "attachments",
            "retrievals",
        ],
        template=file.read(),
        template_format="jinja2",
    )

with open(CFG.relevence_prompt, "r", encoding="utf-8") as file:
    RELEVENCE_PROMPT = PromptTemplate(
        input_variables=["sender", "subject", "body", "attachments"],
        template=file.read(),
        template_format="jinja2",
    )


@traceable(run_type="chain", name="Process Attachments")
async def process_attachments_node(state: AgentState) -> Dict[str, Any]:
    """
    Extract or transcribe attachments (using specialized models) into text and store in state.
    """
    email = state.get("email")
    if not email:
        raise ValueError("AgentState must include 'email' key with EmailMessage")

    texts = await process_attachments(email)
    state["attachments_text"] = texts
    return {"attachments_text": texts}


@traceable(run_type="chain", name="Decide Email Relevance")
async def decide_relevance_node(state: AgentState) -> Dict[str, bool]:
    """
    Uses the LLM to determine if the email is relevant or spam/inappropriate.
    """
    email = state.get("email")
    if not email:
        raise ValueError("AgentState must include 'email' key with EmailMessage")

    attachments_text = state.get("attachments_text", [])

    prompt_content = RELEVENCE_PROMPT.format_prompt(
        sender=email.headers.sender,
        subject=email.headers.subject,
        body=email.body.body_text[
            :1000
        ],  # Limit body length for classification (in case it's purposefully very long)
        attachments="\n".join(attachments_text),
    ).to_string()
    human_message = HumanMessage(content=prompt_content)

    try:
        classification = await RELEVENCE_LLM.ainvoke(
            [human_message]
        )  # Structured output included
        state["is_relevant"] = classification.is_relevant
        logger.info(
            f"Email relevance determined: is_relevant={classification.is_relevant}, reason={classification.reason}"
        )
    except Exception as e:
        logger.error(
            f"Failed to determine relevence: {e}. Defaulting to relevant=True."
        )
        state["is_relevant"] = True

    return {"is_relevant": state.get("is_relevant", True)}


@traceable(run_type="chain", name="Call LLM for Reply")
async def call_model(state: AgentState) -> AgentState:
    """
    Generate a reply or function call based on current state.
    """
    email = state.get("email")
    if not email:
        raise ValueError("AgentState must include 'email' key with EmailMessage")

    history = state.get("history", [])
    attachments_text = state.get("attachments_text", [])
    tool_results_context = state.get(
        "tool_results_context", "No previous tool results."
    )

    prompt_content = SYSTEM_PROMPT.format_prompt(
        sender=email.headers.sender,
        subject=email.headers.subject,
        date=email.headers.date,
        body=email.body.body_text,
        attachments=attachments_text,
        tool_results_context=tool_results_context,
    ).to_string()
    human_message = HumanMessage(content=prompt_content)

    response_message: AIMessage = await LLM_WITH_TOOLS.ainvoke(
        history + [human_message]
    )

    tool_calls = response_message.tool_calls
    if tool_calls:
        state["tool_calls"] = (
            tool_calls  # Store tool call requests for the next node (Execute Tools)
        )
        state["history"] = history + [
            human_message,
            response_message,
        ]  # Append to history
        logger.info(f"LLM requested tool calls: {tool_calls}")
    else:
        # Parse text response
        if type(response_message.content) is list:
            try:
                reply = response_message.content[0]["text"]
            except Exception:
                logger.warning(
                    f"Response content had unexpected formatting: '{response_message.content}' ({type(response_message.content)})"
                )
                reply = str(response_message.content)
        else:
            reply = response_message.content

        state["reply"] = reply
        logger.info(f"LLM provided final reply: {reply[:50]}...")

    return state


@traceable(run_type="tool", name="Execute Tools")
async def execute_tools(state: AgentState) -> AgentState:
    """
    Executes the requested tools and formats the output for the next LLM call.
    """
    tool_calls = state.get("tool_calls", [])
    tool_messages: List[ToolMessage] = []

    for tool_call in tool_calls:
        # Find the function to execute
        tool_func = next((t for t in TOOLS if t.name == tool_call["name"]), None)

        if not tool_func:
            logger.warning(
                f"Tool {tool_call['name']} not found in available tools list."
            )
            tool_messages.append(
                ToolMessage(
                    content=f"Error: Tool {tool_call['name']} is not defined.",
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
            continue

        # Execute the function
        try:
            output = await tool_func.ainvoke(tool_call["args"])
            tool_messages.append(
                ToolMessage(
                    content=str(output),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
            logger.info(f"Tool {tool_call['name']} executed successfully.")

        except Exception as e:
            logger.error(f"Error executing tool {tool_call['name']}: {e}")
            tool_messages.append(
                ToolMessage(
                    content=f"Error executing tool {tool_call['name']}: {e}",
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )

    history = state.get("history", [])
    state["history"] = history + tool_messages

    # Store the formatted results in the state to be passed back to the LLM
    existing_context = state.get("tool_results_context", "")
    new_context = "\n---\n".join([msg.content for msg in tool_messages])

    if existing_context:
        state["tool_results_context"] = existing_context + "\n\n" + new_context
    else:
        state["tool_results_context"] = new_context

    # Reset tool_calls
    state["tool_calls"] = []

    return state


def should_filter_or_continue(state: AgentState) -> Literal["call_model", "filtered"]:
    """
    Routing node:
    - If the email is relevant, proceed to 'call_model'.
    - Otherwise, if it is spam/irrelevant, transition to 'filtered' (= END).
    """
    is_relevant = state.get("is_relevant", True)

    if is_relevant:
        return "call_model"

    return "filtered"


def should_continue(state: AgentState) -> Literal["tool", "final_answer"]:
    """
    Routing node:
    - If the LLM requested a tool, execute the tool.
    - Otherwise, if the LLM provided a final 'reply', end the graph.
    """
    if state.get("tool_calls"):
        return "tool"

    return "final_answer"
