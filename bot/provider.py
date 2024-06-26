import abc
import importlib
import traceback


class Provider(abc.ABC):
    """Abstract base class for AI providers."""

    def __init__(self, provider_name, config):
        """
        Initialize the Provider.

        :param provider_name: Name of the provider
        :param config: Configuration dictionary
        """
        self.provider_name = provider_name
        self.config = config
        self.provider_config = config['providers'][provider_name]

    @abc.abstractmethod
    async def generate_response(self, model, messages, options):
        """
        Generate a response using the Ollama client.

        :param model: The AI model to use
        :param messages: List of input messages
        :param options: Additional options for generation
        :return: Dictionary containing the generated response
        """
        pass

    @abc.abstractmethod
    async def transcribe_voice(self, input_filename):
        """
        Transcribe voice from an audio file using Whisper.

        :param input_filename: Path to the input audio file
        :return: Transcribed text
        """
        pass

    @abc.abstractmethod
    async def text_to_speech(self, text, output_filename, language = "en", speaker = None):
        """
        Convert text to speech using TTS and save as an audio file.

        :param text: Input text to convert
        :param output_filename: Path to save the output audio file
        :return: Result of the TTS conversion
        """
        pass


def get_provider(config):
    """
    Get the provider instance based on the configuration.

    :param config: Configuration dictionary
    :return: Instance of the specified provider
    :raises ValueError: If the provider is unknown or cannot be imported
    """
    provider_signature = config['provider'].split('.')
    provider_name = provider_signature[0]
    provider_class = provider_signature[1]

    try:
        module = importlib.import_module(f"bot.providers.{provider_name}")
        provider_class = getattr(module, provider_class)
        return provider_class(config['provider'], config)
    except (ImportError, AttributeError):
        traceback.print_exc()
        raise ValueError(f"Unknown provider: {provider_signature}")