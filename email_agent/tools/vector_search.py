from langchain.tools import tool
from typing import List
from email_agent.utils.logger import logger
from email_agent.config import CFG
from email_agent.services.ingestion import embedding_model
from langchain_core.documents import Document
from google.cloud import aiplatform
from fastembed import TextEmbedding
from fastembed.common.model_description import PoolingType, ModelSource
from google.cloud import storage


index_endpoint = None
storage_client = None


def get_gcs_file_content(gcs_path):
    """
    Downloads the content of a GCS file blob as a string.
    """
    global storage_client
    logger.info(f"Downloading GCS file: {gcs_path}")
    try:
        if storage_client is None:
            storage_client = storage.Client()

        bucket = storage_client.bucket(CFG.bucket_name)
        blob_name = gcs_path.split(CFG.bucket_name + "/")[-1]
        blob = bucket.blob(blob_name)
        content = blob.download_as_text(encoding="utf-8")

        logger.info(f"Content: {content}")

        return content

    except Exception as e:
        print(f"An error occurred: {e}")
        return "[Unable to download contents of knowledge documents]"


def init_retriever():
    global index_endpoint
    logger.info("Initializing matching engine index endpoint.")
    try:
        index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=CFG.index_endpoint_id
        )

    except Exception as e:
        logger.error(f"Error initializing Vertex AI Search Retriever: {e}")


def init_model():
    global embedding_model
    logger.info("Initializing embedding model.")
    try:
        TextEmbedding.add_custom_model(
            model=CFG.embedding_model_name,
            pooling=PoolingType.MEAN,
            normalization=True,
            sources=ModelSource(hf=CFG.embedding_model_name),
            dim=CFG.vector_dimensions,
            model_file="onnx/model.onnx",
        )

        embedding_model = embedding_model = TextEmbedding(
            model_name=CFG.embedding_model_name
        )

    except Exception as e:
        logger.error(f"Error initializing Vertex AI Search Retriever: {e}")


def get_query_embedding(text: str) -> List[float]:
    """
    Converts a string of text into a vector embedding.
    """
    global embedding_model
    if not embedding_model:
        init_model()

    embeddings = embedding_model.embed([text])
    return list(embeddings)[0]


async def retrieve_context(
    query: str,
) -> List[Document]:
    """
    Uses the embedding of the query string to search for nearest neighbours in the vector search index.
    """
    global index_endpoint

    if not index_endpoint:
        init_retriever()

    logger.info(
        f"Retrieving context for query: '{query[:50]}...' (k={CFG.retriever_k})"
    )
    try:
        query_vector = get_query_embedding(query)

        retrieved_docs = index_endpoint.find_neighbors(
            deployed_index_id=CFG.index_name,
            queries=[query_vector],
            num_neighbors=CFG.retriever_k,
        )[0]

        logger.info(f"Retrieved {len(retrieved_docs)} documents.")
        return retrieved_docs

    except Exception as e:
        logger.error(f"Error during Google Vector Search retrieval: {e}")
        return []


@tool("knowledge_base_search")
async def knowledge_base_search(query: str) -> str:
    """
    Searches the corporate knowledge base/Vector Search index for information
    relevant to the user's email inquiry. The knowledge base contains product
    specifications.

    The input query MUST be a single, well-formed question derived from the email.
    """
    retrieved_docs = await retrieve_context(query)

    logger.info(f"retrieved docs: {retrieved_docs}")

    formatted_results = []
    for i, doc in enumerate(retrieved_docs):
        content = get_gcs_file_content(doc.id)
        formatted_results.append(
            f"--- Document {i + 1} ---\nID: {doc.id}\nContent: {content}\n"
        )

    return "\n".join(formatted_results)
