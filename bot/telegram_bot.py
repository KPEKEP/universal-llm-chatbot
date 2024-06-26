import logging
import asyncio
import traceback
import tempfile
import os
import functools
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    JobQueue,
)
from database.user_data_db import UserDataDB
from models.user_data import UserData
from bot.user_state import UserState
from aiolimiter import AsyncLimiter
from langdetect import detect as detect_language

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

from bot.provider import get_provider

def rate_limit(func):
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        
        if not self.global_limiter.has_capacity(1):
            await update.message.reply_text(await self.loc("NO_GLOBAL_CAPACITY", user_id))
            return

        user_limiter = self.get_user_limiter(user_id)
        if not user_limiter.has_capacity(1):
            await update.message.reply_text(await self.loc("NO_USER_CAPACITY", user_id))
            return

        async with self.global_limiter:
            async with user_limiter:
                return await func(self, update, context, *args, **kwargs)
    return wrapper

def admin_required(func):
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            await update.message.reply_text(await self.loc("ADMIN_PERMISSION_DENIED", user_id))
            return
        return await func(self, update, context, *args, **kwargs)
    return wrapper

def user_access_required(func):
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not await self.check_user_access(user_id):
            await update.message.reply_text(await self.loc("NO_PERMISSION", user_id))
            return
        return await func(self, update, context, *args, **kwargs)
    return wrapper

def user_data_required(func):
    @functools.wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        user_data = await self.user_db.get_user_data(user_id)
        if not user_data:
            await self.user_db.create_user(user_id)
        return await func(self, update, context, *args, **kwargs)
    return wrapper

class TelegramBot:
    """
    A class representing a Telegram bot with various functionalities.
    """

    def __init__(self, config, localization):
        """
        Initialize the TelegramBot with configuration and localization.

        :param config: Dictionary containing bot configuration
        :param localization: Dictionary containing localization strings
        """
        self.config = config
        self.localization = localization

        self.application = Application.builder().token(config["telegram"]["token"]).build()
        self.user_db = UserDataDB(config, config["user_data_db"]["name"])
        self.provider = get_provider(config)
        self.global_limiter = AsyncLimiter(
            config["rate_limit"]["global_max_requests"],
            config["rate_limit"]["global_time_frame_seconds"],
        )
        self.user_limiters = {}
        self.user_max_requests = config["rate_limit"]["user_max_requests"]
        self.user_time_frame_seconds = config["rate_limit"]["user_time_frame_seconds"]
        
        self.job_queue = self.application.job_queue

        self.admin_users = set(config["telegram"]["admin_users"])
        self.access_mode = config["telegram"]["access_mode"]
        
        self.setup_handlers()

    def get_user_limiter(self, user_id):
        if user_id not in self.user_limiters:
            self.user_limiters[user_id] = AsyncLimiter(
                self.user_max_requests,
                self.user_time_frame_seconds
            )
        return self.user_limiters[user_id]
    
    async def loc(self, key, user_id):
        """
        Get localized string for a given key and user ID.

        :param key: Localization key
        :param user_id: User ID
        :return: Localized string
        """
        user_data = await self.user_db.get_user_data(user_id)
        language = user_data.language if user_data else "en"
        return self.localization[language].get(key, key)

    def setup_handlers(self):
        """Set up command and message handlers for the bot."""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("reset", self.reset))
        self.application.add_handler(CommandHandler("settings", self.settings))
        self.application.add_handler(CommandHandler("language", self.language))
        self.application.add_handler(CommandHandler("speaker", self.speaker))
        self.application.add_handler(CommandHandler("history", self.export_history))
        self.application.add_handler(CommandHandler("whitelist", self.admin_whitelist))
        self.application.add_handler(CommandHandler("blacklist", self.admin_blacklist))
        self.application.add_handler(CommandHandler("broadcast", self.admin_broadcast))
        self.application.add_handler(CommandHandler("grant_admin", self.admin_set_admin))
        self.application.add_handler(CallbackQueryHandler(self.button))
        self.application.add_handler(
            MessageHandler(filters.TEXT | filters.VOICE & ~filters.COMMAND, self.handle_message)
        )
        self.application.add_error_handler(self.error)

    @user_data_required
    @rate_limit
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command."""
        user_id = update.effective_user.id
        user_data = await self.user_db.get_user_data(user_id)
        await update.message.reply_text(await self.loc("WELCOME", user_id))

    
    @user_access_required
    @user_data_required
    @rate_limit
    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /reset command to clear message history."""
        if not self.global_limiter.has_capacity(1):
            await update.message.reply_text(await self.loc("NO_GLOBAL_CAPACITY", user_id))
            return
                
        user_id = update.effective_user.id
        user_data = await self.user_db.get_user_data(user_id)
        if user_data:
            user_data.message_history = []
            await self.user_db.update_user_data(user_data)
        await update.message.reply_text(await self.loc("HISTORY_RESET", user_id))

    @user_access_required
    @user_data_required
    @rate_limit
    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /settings command to display and modify bot settings."""
        user_id = update.effective_user.id
        user_data = await self.user_db.get_user_data(user_id)
        if not user_data:
            await self.user_db.create_user(user_id)
            user_data = await self.user_db.get_user_data(user_id)

        current_settings = (
            f"Current settings:\n"
            f"Model: {user_data.model}\n"
            f"System Prompt: {user_data.system_prompt}\n"
            f"Temperature: {user_data.temperature}\n"
            f"Top P: {user_data.top_p}\n"
            f"Max Tokens: {user_data.max_tokens}\n"
        )

        buttons = [
            ("SET_MODEL", "set_model"),
            ("SET_SYSTEM_PROMPT", "set_system_prompt"),
            ("SET_TEMPERATURE", "set_temperature"),
            ("SET_TOP_P", "set_top_p"),
            ("SET_MAX_TOKENS", "set_max_tokens"),
            ("GO_BACK", "back"),
        ]

        keyboard = [
            [InlineKeyboardButton(await self.loc(text, user_id), callback_data=data)]
            for text, data in buttons
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        full_message = f"{current_settings}\n{await self.loc('SETTINGS', user_id)}"

        await update.message.reply_text(full_message, reply_markup=reply_markup)

    @user_access_required
    @user_data_required
    @rate_limit
    async def speaker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /speaker command to change the bot's voice."""
        user_id = update.effective_user.id
        go_back_text = await self.loc("GO_BACK", user_id)
        keyboard = [
            [InlineKeyboardButton(speaker, callback_data=f"set_speaker:{speaker}")]
            for speaker in self.provider.speakers
        ]
        keyboard.append([InlineKeyboardButton(go_back_text, callback_data="back")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            await self.loc("CHOOSE_SPEAKER", user_id), reply_markup=reply_markup
        )

    @user_access_required
    @user_data_required
    @rate_limit
    async def language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /language command to change the bot's language."""
        user_id = update.effective_user.id
        go_back_text = await self.loc("GO_BACK", user_id)
        keyboard = [
            [
                InlineKeyboardButton(
                    self.localization[lang]["LANGUAGE_NAME"],
                    callback_data=f"set_language:{lang}",
                )
            ]
            for lang in self.localization.keys()
        ]
        keyboard.append([InlineKeyboardButton(go_back_text, callback_data="back")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            await self.loc("CHOOSE_LANGUAGE", user_id), reply_markup=reply_markup
        )

    @user_access_required
    @user_data_required
    @rate_limit
    async def button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks from inline keyboards."""        
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        query_data = query.data

        if query_data == "back":
            context.user_data.pop("user_state", None)
            await query.message.edit_text(await self.loc("OK", user_id))
            return

        if "user_state" not in context.user_data:
            context.user_data["user_state"] = UserState()

        state_machine = context.user_data["user_state"]

        if query_data.startswith("set_language:"):
            lang = query_data.split(":", 1)[1]
            await self.set_language(update, context, lang)
        elif query_data.startswith("set_speaker:"):
            speaker = query_data.split(":", 1)[1]
            await self.set_speaker(update, context, speaker)
        elif query_data == "set_model":
            await self.show_model_options(update, context)
        elif query_data.startswith("choose_model:"):
            model = query_data.split(":", 1)[1]
            await self.set_model(update, context, model)
        else:
            await getattr(state_machine, query_data)()

            state_messages = {
                "awaiting_model": "AWAITING_MODEL",
                "awaiting_system_prompt": "AWAITING_SYSTEM_PROMPT",
                "awaiting_temperature": "AWAITING_TEMPERATURE",
                "awaiting_top_p": "AWAITING_TOP_P",
                "awaiting_max_tokens": "AWAITING_MAX_TOKENS",
            }

            await query.message.reply_text(
                await self.loc(state_messages[state_machine.state], user_id)
            )

            # Set a timeout to reset the state after 5 minutes
            context.job_queue.run_once(self.reset_state, 300, data={"user_id": user_id})

    async def show_model_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available model options as buttons."""
        user_id = update.effective_user.id
        available_models = self.provider.provider_config["models"]["available"]
        
        keyboard = [
            [InlineKeyboardButton(model, callback_data=f"choose_model:{model}")]
            for model in available_models
        ]
        keyboard.append([InlineKeyboardButton(await self.loc("GO_BACK", user_id), callback_data="back")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text(
            await self.loc("CHOOSE_MODEL", user_id),
            reply_markup=reply_markup
        )

    async def set_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE, model: str):
        """Set the user's preferred model."""
        user_id = update.effective_user.id
        user_data = await self.user_db.get_user_data(user_id)

        if model in self.provider.provider_config["models"]["available"]:
            if model != user_data.model:
                user_data.model = model
                await self.user_db.update_user_data(user_data)
            response_fmt = await self.loc("MODEL_SET", user_id)
            await update.callback_query.message.edit_text(
                response_fmt.format(value=model)
            )
        else:
            await update.callback_query.message.edit_text(
                await self.loc("MODEL_INVALID", user_id)
            )

    async def set_speaker(self, update: Update, context: ContextTypes.DEFAULT_TYPE, speaker: str):
        """Set the user's preferred voice speaker."""        
        user_id = update.effective_user.id
        user_data = await self.user_db.get_user_data(user_id)

        if speaker in self.provider.speakers:
            if speaker != user_data.speaker:
                user_data.speaker = speaker
                await self.user_db.update_user_data(user_data)
            response_fmt = await self.loc("SPEAKER_SET", user_id)
            await update.callback_query.message.edit_text(
                response_fmt.format(value=speaker)
            )
        else:
            await update.callback_query.message.edit_text(
                await self.loc("SPEAKER_INVALID", user_id)
            )

    async def set_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
        """Set the user's preferred language."""
        user_id = update.effective_user.id
        user_data = await self.user_db.get_user_data(user_id)

        if lang in self.localization:
            if lang != user_data.language:
                user_data.language = lang
                await self.user_db.update_user_data(user_data)
            response_fmt = await self.loc("LANGUAGE_SET", user_id)
            await update.callback_query.message.edit_text(
                response_fmt.format(value=self.localization[lang]["LANGUAGE_NAME"])
            )
        else:
            await update.callback_query.message.edit_text(
                await self.loc("LANGUAGE_INVALID", user_id)
            )

    async def reset_state(self, context: ContextTypes.DEFAULT_TYPE):
        """Reset the user's state after a timeout."""
        user_id = context.job.data["user_id"]
        user_data = context.application.user_data[user_id]
        user_data.pop("user_state", None)

    @user_access_required
    @user_data_required
    @rate_limit
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text and voice messages."""
        user_id = update.effective_user.id
        user_data = await self.user_db.get_user_data(user_id)

        async with self.global_limiter:
            try:
                if (
                    "user_state" in context.user_data
                    and context.user_data["user_state"].state != "idle"
                ):
                    await self.handle_setting_update(update, context, user_data)
                else:
                    # Schedule the message processing as a job
                    context.job_queue.run_once(
                        self.process_message_job,
                        0,
                        data={
                            "update": update,
                            "user_data": user_data,
                            "context": context
                        }
                    )
                    await update.message.reply_chat_action("typing")
            except Exception as e:
                logger.error(f"Error scheduling message processing: {str(e)}")
                traceback.print_exc()
                await update.message.reply_text(await self.loc("HANDLING_ERROR", user_id))

    async def process_message_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Job to process the message in the background."""
        job_data = context.job.data
        update = job_data["update"]
        user_data = job_data["user_data"]
        
        try:
            await self.process_message(update, user_data)
        except Exception as e:
            logger.error(f"Error in process_message_job: {str(e)}")
            traceback.print_exc()
            user_id = update.effective_user.id
            await update.message.reply_text(await self.loc("PROCESSING_ERROR", user_id))

    async def transcribe_voice(self, update: Update):
        """Transcribe a voice message to text."""
        voice_file = await update.message.voice.get_file()
        voice_bytes = await voice_file.download_as_bytearray()

        temp_ogg_filename = None
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_ogg:
            temp_ogg.write(voice_bytes)
            temp_ogg_filename = temp_ogg.name
        try:
            message, language = await self.provider.transcribe_voice(temp_ogg_filename)
            logger.info(f"Detected voice language: {language}")
            return message, language
        except Exception as e:
            logger.error(f"Error during voice transcription: {str(e)}")
            raise
        finally:
            if temp_ogg_filename is not None:
                os.unlink(temp_ogg_filename)

    async def send_voice_response(self, update: Update, ai_message: str, language:str, user_data: UserData):
        """Generate and send a voice response."""
        user_id = update.effective_user.id
        try:
            temp_wav_filename = None
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                temp_wav_filename = temp_wav.name
            
            await self.provider.text_to_speech(ai_message, temp_wav_filename, language, user_data.speaker)
            
            with open(temp_wav_filename, "rb") as audio:
                await update.message.reply_voice(voice=audio)
        except Exception as e:
            logger.error(f"Error in voice response generation: {str(e)}")
            traceback.print_exc()
            await update.message.reply_text(
                (await self.loc("VOICE_ERROR_SORRY", user_id)) + ai_message
            )
        finally:
            if temp_wav_filename is not None:
                os.unlink(temp_wav_filename)


    async def process_message(self, update: Update, user_data: UserData):
        """Process incoming messages and generate responses."""
        try:
            user_id = update.effective_user.id

            language = user_data.language

            if update.message.voice:
                user_message, language = await self.transcribe_voice(update)
            else:
                user_message = update.message.text

            system_prompt = {"role": "system", "content": user_data.system_prompt}
            user_prompt = {"role": "user", "content": user_message}            
            messages = [system_prompt] + user_data.message_history
            
            if self.config['remind_system_prompt']:
                messages = messages + [system_prompt]

            messages = messages + [user_prompt]
            
            response = await self.provider.generate_response(
                model=user_data.model,
                messages=messages,
                options={
                    "temperature": user_data.temperature,
                    "top_p": user_data.top_p,
                    "max_tokens": user_data.max_tokens
                },
            )

            ai_message = response["content"]
            language = detect_language(ai_message)
            logger.info(f"Detected response language: {language}")
            user_data.message_history.append(user_prompt)
            user_data.message_history.append({"role": "assistant", "content": ai_message})

            user_data.last_request = datetime.now()
            await self.user_db.update_user_data(user_data)

            try:
                if update.message.voice:
                    await self.send_voice_response(update, ai_message, language, user_data)
                else:
                    await update.message.reply_text(ai_message)
            except Exception as e:
                logger.error(f"Error in send_voice_response: {str(e)}")
                traceback.print_exc()
                await update.message.reply_text(
                    f"{await self.loc('VOICE_ERROR_SORRY', user_id)}{ai_message}"
                )

        except Exception as e:
            logger.error(f"Error in process_message: {str(e)}")
            traceback.print_exc()
            await update.message.reply_text(await self.loc("PROCESSING_ERROR", user_id))

    async def handle_setting_update(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_data: UserData
    ):
        """Handle updates to user settings."""
        user_id = update.effective_user.id
        state_machine = context.user_data["user_state"]
        value = update.message.text

        if state_machine.state == "awaiting_model":
            await self.update_model(update, user_data, value)
        elif state_machine.state in ["awaiting_temperature", "awaiting_top_p"]:
            await self.update_float_setting(
                update, user_data, state_machine.state.split("_", 1)[1], value
            )
        elif state_machine.state == "awaiting_max_tokens":
            await self.update_max_tokens(update, user_data, value)
        else:
            await self.update_setting(
                update, user_data, state_machine.state.split("_", 1)[1], value
            )

        await state_machine.return_to_idle()

    async def update_model(self, update: Update, user_data: UserData, value: str):
        """Update the user's preferred model."""
        user_id = update.effective_user.id
        if value in self.provider.provider_config["models"]["available"]:
            if value != user_data.model:
                user_data.model = value
                await self.user_db.update_user_data(user_data)
            await update.message.reply_text(
                (await self.loc("MODEL_SET", user_id)).format(value=value)
            )
        else:
            await update.message.reply_text(await self.loc("MODEL_INVALID", user_id))

    async def update_float_setting(
        self, update: Update, user_data: UserData, param: str, value: str
    ):
        """Update a float setting (temperature or top_p) for the user."""
        user_id = update.effective_user.id
        try:
            value = float(value)
            if 0 <= value <= 1:
                old_value = getattr(user_data, param)
                if value != old_value:
                    setattr(user_data, param, value)
                    await self.user_db.update_user_data(user_data)
                await update.message.reply_text(
                    (await self.loc("PARAM_SET", user_id)).format(
                        param=param.capitalize(), value=value
                    )
                )
            else:
                await update.message.reply_text(
                    (await self.loc("PARAM_INVALID_VALUE", user_id)).format(
                        param=param.capitalize()
                    )
                )
        except ValueError:
            await update.message.reply_text(
                (await self.loc("PARAM_INVALID_VALUE", user_id)).format(
                    param=param.capitalize()
                )
            )

    async def update_max_tokens(self, update: Update, user_data: UserData, value: str):
        """Update the max_tokens setting for the user."""
        user_id = update.effective_user.id
        try:
            value = int(value)
            if value > 0:
                if value != user_data.max_tokens:
                    user_data.max_tokens = value
                    await self.user_db.update_user_data(user_data)
                await update.message.reply_text(
                    (await self.loc("MAX_TOKENS_SET", user_id)).format(value=value)
                )
            else:
                await update.message.reply_text(await self.loc("MAX_TOKENS_INVALID", user_id))
        except ValueError:
            await update.message.reply_text(await self.loc("MAX_TOKENS_INVALID", user_id))

    async def update_setting(
        self, update: Update, user_data: UserData, param: str, value: str
    ):
        """Update a general setting for the user."""
        user_id = update.effective_user.id
        old_value = getattr(user_data, param)
        if value != old_value:
            setattr(user_data, param, value)
            await self.user_db.update_user_data(user_data)
        await update.message.reply_text(
            (await self.loc("PARAM_SET", user_id)).format(param=param.capitalize())
        )

    @user_access_required
    @user_data_required
    @rate_limit
    async def export_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export user's message history as a txt file."""
        user_id = update.effective_user.id
        user_data = await self.user_db.get_user_data(user_id)

        if not user_data.message_history:
            await update.message.reply_text(await self.loc("NO_HISTORY", user_id))
            return

        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt', encoding='utf-8') as temp_file:
            for message in user_data.message_history:
                temp_file.write(f"{message['role'].capitalize()}: {message['content']}\n\n")

        try:
            with open(temp_file.name, 'rb') as file:
                await update.message.reply_document(document=file, filename="message_history.txt")
        except Exception as e:
            logger.error(f"Error sending history file: {str(e)}")
            await update.message.reply_text(await self.loc("HISTORY_EXPORT_ERROR", user_id))
        finally:
            os.unlink(temp_file.name)

    @admin_required
    @user_data_required
    async def admin_whitelist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Whitelist a user. Only admins can use this command.
        Usage: /whitelist <user_id>
        """
        user_id = update.effective_user.id
        
        target_user_id = int(context.args[0])
        mode = True
        if len(context.args) > 1:
            mode_arg = str(context.args[1]).lower()
            mode_off = (mode_arg == "false") or (mode_arg == "0") or (mode_arg == "off") or (mode_arg == "no")            
            mode = not mode_off        
        await self.user_db.set_whitelist(target_user_id, mode)
        await update.message.reply_text((await self.loc("USER_WHITELISTED", user_id)).format(user_id=target_user_id, mode=mode))

    @admin_required
    @user_data_required
    async def admin_blacklist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Blacklist a user. Only admins can use this command.
        Usage: /blacklist <user_id>
        """
        user_id = update.effective_user.id
        
        target_user_id = int(context.args[0])
        mode = True
        if len(context.args) > 1:
            mode_arg = str(context.args[1]).lower()
            mode_off = (mode_arg == "false") or (mode_arg == "0") or (mode_arg == "off") or (mode_arg == "no")            
            mode = not mode_off
        await self.user_db.set_blacklist(target_user_id, mode)
        await update.message.reply_text((await self.loc("USER_BLACKLISTED", user_id)).format(user_id=target_user_id, mode=mode))

    @admin_required
    @user_data_required
    async def admin_blacklist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Blacklist a user. Only admins can use this command.
        Usage: /blacklist <user_id>
        """
        user_id = update.effective_user.id
        
        target_user_id = int(context.args[0])
        mode = True
        if len(context.args) > 1:
            mode_arg = str(context.args[1]).lower()
            mode_off = (mode_arg == "false") or (mode_arg == "0") or (mode_arg == "off") or (mode_arg == "no")            
            mode = not mode_off
        await self.user_db.set_blacklist(target_user_id, mode)
        await update.message.reply_text((await self.loc("USER_BLACKLISTED", user_id)).format(user_id=target_user_id, mode=mode))

    @admin_required
    @user_data_required
    async def admin_set_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Promotes\demotes user from being admin. Only admins can use this command.
        Usage: /grant_admin <user_id>
        """
        user_id = update.effective_user.id
        
        target_user_id = int(context.args[0])
        mode = True
        if len(context.args) > 1:
            mode_arg = str(context.args[1]).lower()
            mode_off = (mode_arg == "false") or (mode_arg == "0") or (mode_arg == "off") or (mode_arg == "no")            
            mode = not mode_off
        await self.user_db.set_admin(target_user_id, mode)
        await update.message.reply_text((await self.loc("USER_ADMINED", user_id)).format(user_id=target_user_id, mode=mode))

    @admin_required
    @user_data_required
    async def admin_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Broadcast a message to all users. Only admins can use this command.
        Usage: /broadcast <message>
        """
        user_id = update.effective_user.id
        
        message = ' '.join(context.args)
        all_users = await self.user_db.get_all_users()
        for user_id in all_users:
            try:
                await context.bot.send_message(chat_id=user_id, text=message)
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {str(e)}")
        
        await update.message.reply_text(await self.loc("BROADCAST_SENT", user_id))

    async def is_admin(self, user_id: int) -> bool:
        """
        Check if a user is an admin.
        :param user_id: The user ID to check
        :return: True if the user is an admin, False otherwise
        """
        if user_id in self.admin_users:
            return True
        user_data = await self.user_db.get_user_data(user_id)
        return user_data.is_admin if user_data else False

    async def check_user_access(self, user_id: int) -> bool:
        """
        Check if a user has access to use the bot.
        :param user_id: The user ID to check
        :return: True if the user has access, False otherwise
        """
        user_data = await self.user_db.get_user_data(user_id)
        if not user_data:
            return False
        if user_data.is_blacklisted:
            return False
        if self.access_mode == "whitelist" and not user_data.is_whitelisted:
            return False
        return True    
            
    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Log errors caused by updates and report to admin users."""
        user_id = update.effective_user.id if update.effective_user else None
        logger.error(f"Update {update} caused error {context.error}")
        
        error_message = f"An error occurred while processing an update:\n\n{str(context.error)}"
        stack_trace = ''.join(traceback.format_tb(context.error.__traceback__))
        
        admin_users = await self.user_db.get_admins()
        
        for admin_id in admin_users:
            try:
                await context.bot.send_message(chat_id=admin_id, text=error_message)
                temp_file_name = None
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
                    temp_file.write(stack_trace)
                    temp_file.seek(0)
                    temp_file_name = temp_file.name
                    await context.bot.send_document(chat_id=admin_id, document=temp_file.name, filename="error_stack_trace.txt")                
            except Exception as e:
                logger.error(f"Failed to send error report to admin {admin_id}: {str(e)}")
            finally:
                if temp_file_name is not None:
                    os.unlink(temp_file_name)
        
        if update.effective_message:
            await update.effective_message.reply_text(await self.loc("ERROR_SORRY", user_id))

    def run(self):
        """Run the bot."""
        async def main():
            stop_event = asyncio.Event()

            async def startup():
                await self.user_db.setup_database()
                logger.info("DB Started")
                await self.application.initialize()
                logger.info("App Initialized")
                await self.application.start()
                logger.info("App Started")
                logger.info("Starting polling")
                await self.application.updater.start_polling()

            async def shutdown():
                await self.user_db.disconnect()
                await self.application.stop()
                logger.info("App Stopped")
                await self.application.shutdown()
                logger.info("App shut down")

            try:
                await startup()
                logger.info("Bot is running. Press Ctrl+C to stop.")
                await stop_event.wait()
            except KeyboardInterrupt:
                logger.info("Stopping bot...")
            finally:
                await shutdown()

        asyncio.run(main())