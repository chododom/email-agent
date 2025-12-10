from typing import List
from email_agent.config import CFG
from email_agent.utils.logger import logger
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_google_community import GCSFileLoader

from google.cloud.aiplatform_v1 import (
    UpsertDatapointsRequest,
    IndexServiceAsyncClient,
    IndexDatapoint,
)
from fastembed import TextEmbedding
from fastembed.common.model_description import PoolingType, ModelSource


index_service_client = IndexServiceAsyncClient(
    client_options={"api_endpoint": f"{CFG.region}-aiplatform.googleapis.com"}
)
embedding_model = None


def load_and_chunk_gcs_file(bucket_name: str, file_name: str) -> List[Document]:
    """
    Loads text from GCS using LangChain's loader and splits it recursively.
    """
    # Use GCSFileLoader to download document blobs
    loader = GCSFileLoader(
        project_name=CFG.project_id, bucket=bucket_name, blob=file_name
    )
    documents = loader.load()

    # Chunk the documents, prioritizing keeping semantic units together
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=50,
        length_function=len,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks = text_splitter.split_documents(documents)

    logger.info(f"File {file_name} loaded and split into {len(chunks)} documents.")
    return chunks


def get_multilingual_embeddings(chunks: List[str]) -> List[List[float]]:
    """
    Generates vector embeddings for a list of document chunks.
    """
    global embedding_model

    if embedding_model is None:
        try:
            TextEmbedding.add_custom_model(
                model=CFG.embedding_model_name,
                pooling=PoolingType.MEAN,
                normalization=True,
                sources=ModelSource(hf=CFG.embedding_model_name),
                dim=CFG.vector_dimensions,
                model_file="onnx/model.onnx",
            )
        except Exception:
            logger.info(
                f"Embedding model {CFG.embedding_model_name} already added to 'fastembed'."
            )

        embedding_model = embedding_model = TextEmbedding(
            model_name=CFG.embedding_model_name
        )

    embeddings = embedding_model.embed([chunk.page_content for chunk in chunks])

    return list(embeddings)


async def upsert_to_vector_search(embeddings: List[List[float]], documents):
    """
    Upserts datapoints to the Vertex AI Vector Search Index.
    """
    datapoints = []
    for vector, doc in zip(embeddings, documents):
        datapoints.append(
            IndexDatapoint(
                datapoint_id=doc.metadata[
                    "source"
                ],  # Later to be returned by the query of the index
                feature_vector=vector,
            )
        )

    request = UpsertDatapointsRequest(index=CFG.index_id, datapoints=datapoints)

    await index_service_client.upsert_datapoints(request=request)

    logger.info(
        f"Successfully upserted {len(datapoints)} datapoints to {CFG.index_id}."
    )
