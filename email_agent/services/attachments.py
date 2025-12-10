from typing import List
import io
from langsmith import traceable
from email_agent.models.gmail import EmailMessage
from email_agent.utils.logger import logger
from email_agent.config import CFG


image_model = None
with open(CFG.description_prompt_path, "r", encoding="utf-8") as file:
    img_description_prompt = file.read()


def _extract_pdf_text(data: bytes) -> str:
    """
    Extracts text from PDFs attached to the email, to be used as further context for the agent.
    """
    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(io.BytesIO(data))
        texts = []
        for page in reader.pages:
            texts.append(page.extract_text() or "")

        pdf_text = "\n".join(texts).strip()
        logger.info(f"PDF text:\n{pdf_text}")
        return pdf_text
    except Exception:
        return "[Extraction of PDF content failed]"


@traceable
async def _extract_image_text(data: bytes) -> str:
    """
    Uses LLM to generate an image description of images attached to the email, to be used as further context for the agent.
    """
    global image_model, img_description_prompt
    try:
        from vertexai.generative_models import (
            GenerationConfig,
            GenerativeModel,
            Part,
            Image,
        )

        image_part = Part.from_image(Image.from_bytes(data))

        if image_model is None:
            image_model = GenerativeModel("gemini-2.5-flash")

        response = await image_model.generate_content_async(
            [image_part, Part.from_text(img_description_prompt)],
            generation_config=GenerationConfig(
                response_mime_type="text/plain",
                temperature=CFG.temperature,
            ),
        )

        description = response.candidates[0].content.parts[0].text
        logger.info(f"Image description:\n{description}")

        return description

    except Exception as e:
        logger.error(f"Failed to generate image description {e}")
        return "[Extraction of image content failed]"


def _extract_audio_text(data: bytes, mime: str) -> str:
    """
    Transcribes audio files attached to the email using Google's Speech-to-Text API, to be used as further context for the agent.
    """
    try:
        from google.cloud import speech

        # Map common MIME types to Speech-to-Text AudioEncoding constants
        MIME_TO_ENCODING = {
            "audio/mpeg": speech.RecognitionConfig.AudioEncoding.MP3,
            "audio/mp3": speech.RecognitionConfig.AudioEncoding.MP3,
            "audio/wav": speech.RecognitionConfig.AudioEncoding.LINEAR16,
            "audio/flac": speech.RecognitionConfig.AudioEncoding.FLAC,
            "audio/ogg": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            "audio/ogg; codecs=opus": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            "audio/mp4": speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED,
            "audio/aac": speech.RecognitionConfig.AudioEncoding.LINEAR16,
        }

        client = speech.SpeechClient()
        audio = speech.RecognitionAudio(content=data)

        mime_lower = mime.lower().split(";")[0].strip()
        enc = MIME_TO_ENCODING.get(mime_lower)

        if enc is None:
            logger.warning(
                "Unable to match encoding, falling back to encoding unspecified"
            )
            enc = speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED

        logger.info(
            f"Attempting audio transcription for MIME {mime_lower} with encoding {enc}"
        )
        config = speech.RecognitionConfig(
            encoding=enc,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
        )

        response = client.recognize(config=config, audio=audio)

        # Get the most likely transcription
        transcription = response.results[0].alternatives[0].transcript
        logger.info(f"Audio transcription: {transcription}")

        return transcription

    except Exception:
        return "[Extraction of audio content failed]"


async def process_attachments(email_message: EmailMessage) -> List[str]:
    """
    Return a list of extracted text summaries for all attachments.
    """
    out: List[str] = []
    for att in email_message.body.attachments or []:
        mime = (att.mime_type or "").lower()
        if "pdf" in mime or att.filename.lower().endswith(".pdf"):
            pdf_text = _extract_pdf_text(att.data)
            out.append(f"PDF ({att.filename}) content:\n{pdf_text}")
        elif mime.startswith("image/"):
            image_text = await _extract_image_text(att.data)
            out.append(f"Image ({att.filename}) content:\n{image_text}")
        elif mime.startswith("audio/"):
            audio_text = _extract_audio_text(att.data, mime)
            out.append(f"Audio ({att.filename}) content:\n{audio_text}")
        else:
            out.append(
                f"[Unsupported attachment {att.filename} of type {att.mime_type}]"
            )

    return out
