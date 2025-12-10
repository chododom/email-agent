from langchain_google_vertexai import ChatVertexAI

from email_agent.config import CFG


llm = ChatVertexAI(
    project=CFG.project_id,
    model=CFG.model_name,
    temperature=CFG.temperature,
)
