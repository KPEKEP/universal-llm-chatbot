# Universal LLM ChatBot

Universal LLM ChatBot is a versatile Telegram bot that leverages Large Language Models (LLMs) for natural language processing, voice transcription, and text-to-speech capabilities. It supports multiple languages and provides a customizable interface for interacting with AI models.

## Features

- Multi-language support
- Voice message transcription
- Text-to-speech responses
- Customizable AI model settings
- User-specific configurations
- Rate limiting to prevent abuse
- Admin commands for user management

## Prerequisites

- Python 3.8+
- Telegram Bot Token (obtain from BotFather)
- Ollama server running locally or remotely

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/KPEKEP/universal-llm-chatbot.git
   cd universal-llm-chatbot
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Copy the `config_template.yml` to `config.yml` and update it with your settings:
   ```
   cp config_template.yml config.yml
   ```

4. Edit `config.yml` to include your Telegram Bot Token and other configurations.

## Configuration

The `config.yml` file contains all the necessary settings for the bot. Key configurations include:

- Telegram bot token
- Admin user IDs
- Access mode (public or whitelist)
- AI provider settings
- Rate limiting parameters

Refer to the comments in `config_template.yml` for detailed explanations of each setting.

## Usage

To start the bot, run:

```
python main.py
```

The bot will now be active and respond to messages on Telegram.

## Extending Beyond BasicProvider

The Universal LLM ChatBot is designed to be extensible. To create a new provider:

1. Create a new file in the `bot/providers/` directory (e.g., `custom_provider.py`).
2. Implement a class that inherits from the `Provider` base class in `bot/provider.py`.
3. Override the abstract methods: `generate_response`, `transcribe_voice`, and `text_to_speech`.
4. Update the `config.yml` to use your new provider.

Example:

```python
from bot.provider import Provider

class CustomProvider(Provider):
    def __init__(self, provider_name, config):
        super().__init__(provider_name, config)
        # Initialize your custom provider here

    async def generate_response(self, model, messages, options):
        # Implement your custom response generation logic

    async def transcribe_voice(self, input_filename):
        # Implement your custom voice transcription logic

    async def text_to_speech(self, text, output_filename, language="en", speaker=None):
        # Implement your custom text-to-speech logic
```

## Ollama Setup

For detailed instructions on setting up Ollama for local inference, please refer to the [Ollama documentation](https://github.com/jmorganca/ollama).

## Acknowledgements

This project utilizes several open-source libraries and models:

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for Telegram integration
- [Ollama](https://github.com/jmorganca/ollama) for local LLM inference
- [Whisper](https://github.com/openai/whisper) for voice transcription
- [Coqui TTS](https://github.com/coqui-ai/TTS) for text-to-speech generation

## Appreciation

If you use this project in your research or application, please give it a star

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.