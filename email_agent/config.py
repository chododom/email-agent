from pydantic_settings import BaseSettings
from pydantic import SecretStr
from email_agent.utils.logger import logger


class Config(BaseSettings):
    package_name: str = "email_agent"
    log_level: str = "INFO"

    project_id: str = "alza-email-agent"
    region: str = "europe-west3"

    user_email: str

    # PubSub
    pubsub_topic: str = f"projects/{project_id}/topics/gmail-inbox-topic"
    gmail_service_acc_json: SecretStr

    # Firestore
    firestore_name: str = "email-agent-db"
    firestore_config_collection: str = "agent_config"
    gmail_state_doc_id: str = "gmail_watch_state"

    # LLM settings
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.0
    sys_prompt_path: str = "email_agent/prompts/system_prompt.txt"
    description_prompt_path: str = "email_agent/prompts/image_description.txt"
    relevence_prompt: str = "email_agent/prompts/relevence_prompt.txt"

    # RAG
    index_id: str = (
        "projects/alza-email-agent/locations/europe-west3/indexes/5437049814980231168"
    )
    index_endpoint_id: str = "7131247699801669632"
    index_name: str = "rag_index_deployment2"
    vector_dimensions: int = 384
    embedding_model_name: str = "intfloat/multilingual-e5-small"
    retriever_k: int = 3
    bucket_name: str = "vector-data-source-alza-email-agent"

    # model_config = SettingsConfigDict(env_file=".env")


CFG = Config()

logger.setLevel(CFG.log_level)
logger.info(f"Config: {CFG}")
