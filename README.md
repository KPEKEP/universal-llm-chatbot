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
- Ollama, Groq, Gemini, OpenAI, and Anthropic support

## Prerequisites

- Python 3.10+
- Telegram Bot Token (obtain from BotFather)
- Ollama server running locally or remotely
- PyTorch development environment (see setup instructions below)

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

4. Set up the required environment variables (see Configuration section).

## PyTorch Development Environment Setup

To set up a PyTorch development environment using Conda, follow these steps:

1. Install Anaconda or Miniconda if you haven't already.

2. Create a new Conda environment:
   ```
   conda create -n pytorch-env python=3.10
   ```

3. Activate the environment:
   ```
   conda activate pytorch-env
   ```

4. Install PyTorch and related packages:
   ```
   conda install pytorch torchvision torchaudio cudatoolkit=11.3 -c pytorch
   ```

5. Install other required packages:
   ```
   pip install -r requirements.txt
   ```

## Configuration

The bot uses a combination of environment variables and a `config.yml` file for configuration.

### Environment Variables

Set the following environment variables:

- `UNI_LLM_BOT_TOKEN`: Your Telegram Bot Token
- `UNI_LLM_ADMIN_USER`: Comma-separated list of admin user IDs
- `UNI_LLM_ACCESS_MODE`: Set to either "public" or "whitelist"

Example:
```bash
export UNI_LLM_BOT_TOKEN=your_bot_token_here
export UNI_LLM_ADMIN_USER=123456789,987654321
export UNI_LLM_ACCESS_MODE=public
export UNI_LLM_GROQ_API_KEY=your_groq_api_key_here
export UNI_LLM_GEMINI_API_KEY=your_gemini_api_key_here
export UNI_LLM_OPENAI_API_KEY=your_openai_api_key_here
export UNI_LLM_ANTHROPIC_API_KEY=your_anthropic_api_key_here

```

### Config File

The `config.yml` file contains additional settings for the bot. Key configurations include:

- AI provider settings
- Rate limiting parameters
- Database settings

Refer to the comments in `config_template.yml` for detailed explanations of each setting.

## Usage

To start the bot, you can use the provided `start.bat` file as an example. Here's a sample content of `start.bat`:

```batch
SET UNI_LLM_BOT_TOKEN=your_telegram_bot_token_here
SET UNI_LLM_ADMIN_USER_IDS=your_telegram_user_id_here
SET UNI_LLM_ACCESS_MODE=public
SET UNI_LLM_GROQ_API_KEY=your_groq_api_key_here
SET UNI_LLM_GEMINI_API_KEY=your_gemini_api_key_here
SET UNI_LLM_OPENAI_API_KEY=your_openai_api_key_here
SET UNI_LLM_ANTHROPIC_API_KEY=your_anthropic_api_key_here

@call conda activate pytorch-env
@call python main.py
```

Modify the `start.bat` file with your specific environment variables and run it to start the bot.

## Available Commands

### User Commands

- `/start`: Initialize the bot and receive a welcome message.
- `/settings`: Access and modify bot settings.
- `/reset`: Reset your conversation history.
- `/history`: Export your conversation history.
- `/language`: Change the bot's language.
- `/speaker`: Change the bot's voice speaker.

### Admin Commands

- `/whitelist <user_id or username> [on/off]`: Add or remove a user from the whitelist.
- `/blacklist <user_id or username> [on/off]`: Add or remove a user from the blacklist.
- `/grant_admin <user_id or username> [on/off]`: Grant or revoke admin privileges for a user.
- `/broadcast <message>`: Send a message to all users.
- `/getid <username>`: Get the user ID for a given username.

### Command Usage Examples

1. Whitelist a user:
   ```
   /whitelist @username on
   ```

2. Blacklist a user:
   ```
   /blacklist 123456789 on
   ```

3. Grant admin privileges:
   ```
   /grant_admin @username on
   ```

4. Send a broadcast message:
   ```
   /broadcast Hello, this is an important announcement!
   ```

5. Get a user's ID:
   ```
   /getid @username
   ```

Note: Admin commands are only available to users with administrative privileges as defined in the `UNI_LLM_ADMIN_USER` environment variable.

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

    async def get_models(self):
        # Implement your custom available models list retrieval logic
        pass        
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