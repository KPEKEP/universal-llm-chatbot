import os
import ollama
from ollama import AsyncClient
import groq
from google.generativeai import GenerativeModel
import openai
from anthropic import AsyncAnthropic
from bot.provider import Provider
import whisper
from TTS.api import TTS
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import google.generativeai as genai

class BasicProvider(Provider):
    """Basic provider implementation using various text providers, Whisper, and TTS."""

    def __init__(self, provider_name, config):
        """
        Initialize the BasicProvider.

        :param provider_name: Name of the provider
        :param config: Configuration dictionary
        """
        super().__init__(provider_name, config)
        self.text_provider = self.provider_config['text_provider']
        
        if self.text_provider == 'ollama':            
            model = self.provider_config['models']['default']
            logging.info(f"Pulling Ollama model: {model}")
            ollama.pull(model)
            logging.info(f"Successfully pulled Ollama model: {model}")
            self.ollama_client = AsyncClient(host=self.provider_config['ollama']['host'])
        elif self.text_provider == 'groq':
            api_key = os.getenv('UNI_LLM_GROQ_API_KEY')
            if not api_key:
                raise ValueError("GROQ API key not found. Please set the UNI_LLM_GROQ_API_KEY environment variable.")
            self.groq_client = groq.AsyncClient(api_key=api_key)
        elif self.text_provider == 'gemini':
            api_key = os.getenv('UNI_LLM_GEMINI_API_KEY')
            if not api_key:
                raise ValueError("Gemini API key not found. Please set the UNI_LLM_GEMINI_API_KEY environment variable.")
            genai.configure(api_key=api_key)
            self.gemini_client = GenerativeModel(self.provider_config['gemini']['model'])
        elif self.text_provider == 'chatgpt':
            api_key = os.getenv('UNI_LLM_OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OpenAI API key not found. Please set the UNI_LLM_OPENAI_API_KEY environment variable.")
            self.openai_client = openai.AsyncOpenAI(api_key=api_key)
        elif self.text_provider == 'claude':
            api_key = os.getenv('UNI_LLM_ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("Anthropic API key not found. Please set the UNI_LLM_ANTHROPIC_API_KEY environment variable.")
            self.claude_client = AsyncAnthropic(api_key=api_key)
        else:
            raise ValueError(f"Unsupported text provider: {self.text_provider}")
        
        self.whisper_model = whisper.load_model(
            self.provider_config["voice"]["whisper_model"]
        )
        self.tts = TTS(self.provider_config["tts"]["model"], gpu=self.provider_config["tts"]["gpu"])
        self.speakers = list(self.tts.synthesizer.tts_model.speaker_manager.name_to_id)

    async def get_models(self):
        if self.text_provider == 'ollama':
            models = await self.ollama_client.list()
            return [model['name'] for model in models['models']]
        elif self.text_provider == 'groq':
            return self.provider_config["groq"]["available_models"]
        elif self.text_provider == 'gemini':
            return self.provider_config["gemini"]["available_models"]
        elif self.text_provider == 'chatgpt':
            models = await self.openai_client.models.list()
            return [model.id for model in models.data if model.id.startswith('gpt')]
        elif self.text_provider == 'claude':
            return self.provider_config["claude"]["available_models"]
        else:
            raise ValueError(f"Unsupported text provider: {self.text_provider}")

    async def generate_response(self, model, messages, options):
        """
        Generate a response using the selected text provider.

        :param model: The AI model to use
        :param messages: List of input messages
        :param options: Additional options for generation
        :return: Dictionary containing the generated response
        """
        if self.text_provider == 'ollama':
            response = await self.ollama_client.chat(
                model=model,
                messages=messages,
                stream=False,
                options=options
            )
            return {'content': response['message']['content']}
        elif self.text_provider == 'groq':
            response = await self.groq_client.chat.completions.create(
                model=model,
                messages=messages,
                **options
            )
            return {'content': response.choices[0].message.content}
        elif self.text_provider == 'gemini':
            response = await self.gemini_client.generate_content_async(messages[-1]['content'])
            return {'content': response.text}
        elif self.text_provider == 'chatgpt':
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                **options
            )
            return {'content': response.choices[0].message.content}
        elif self.text_provider == 'claude':
            response = await self.claude_client.completions.create(
                model=model,
                prompt=messages[-1]['content'],
                **options
            )
            return {'content': response.completion}
        else:
            raise ValueError(f"Unsupported text provider: {self.text_provider}")

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