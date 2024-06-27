import ollama
from ollama import AsyncClient
from bot.provider import Provider
import whisper
from TTS.api import TTS
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

class BasicProvider(Provider):
    """Basic provider implementation using Ollama, Whisper, and TTS."""

    def __init__(self, provider_name, config):
        """
        Initialize the BasicProvider.

        :param provider_name: Name of the provider
        :param config: Configuration dictionary
        """
        super().__init__(provider_name, config)
        
        for model in self.provider_config['models']['available']:
            logging.info(f"Pulling Ollama model: {model}")
            ollama.pull(model)
            logging.info(f"Successfully pulled Ollama model: {model}")

        self.client = AsyncClient(host=self.provider_config['ollama']['host'])
        self.whisper_model = whisper.load_model(
            self.provider_config["voice"]["whisper_model"]
        )
        self.tts = TTS(self.provider_config["tts"]["model"], gpu=self.provider_config["tts"]["gpu"])
        self.speakers = list(self.tts.synthesizer.tts_model.speaker_manager.name_to_id)

    async def generate_response(self, model, messages, options):
        """
        Generate a response using the Ollama client.

        :param model: The AI model to use
        :param messages: List of input messages
        :param options: Additional options for generation
        :return: Dictionary containing the generated response
        """
        response = await self.client.chat(
            model=model,
            messages=messages,
            stream=False,
            options=options
        )
        return {'content': response['message']['content']}

    async def transcribe_voice(self, input_filename):
        """
        Transcribe voice from an audio file using Whisper asynchronously.

        :param input_filename: Path to the input audio file
        :return: Transcribed text and detected language
        """
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, self.whisper_model.transcribe, input_filename)
        transcribed_text = result["text"]
        return transcribed_text, result["language"]

    async def text_to_speech(self, text, output_filename, language = "en", speaker = None):
        """
        Convert text to speech using TTS and save as an audio file asynchronously.

        :param text: Input text to convert
        :param output_filename: Path to save the output audio file
        :return: Result of the TTS conversion
        """
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool,
                self.tts.tts_to_file,
                text,
                speaker,
                language,
                None,
                None,
                float(self.provider_config["tts"]["speaker_speed"]),
                None,
                output_filename,
                self.provider_config["tts"]["split_sentences"]
            )
        return result
