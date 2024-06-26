from transitions.extensions.asyncio import AsyncMachine


class UserState(AsyncMachine):
    """
    Represents the state of a user's interaction with the bot.
    Inherits from AsyncMachine to handle asynchronous state transitions.
    """

    def __init__(self):
        """
        Initialize the UserState with predefined states and transitions.
        """
        states = [
            'idle',
            'awaiting_model',
            'awaiting_system_prompt',
            'awaiting_temperature',
            'awaiting_top_p',
            'awaiting_max_tokens'
        ]
        
        AsyncMachine.__init__(self, states=states, initial='idle')

        # Define transitions from idle state to various awaiting states
        self.add_transition('set_model', 'idle', 'awaiting_model')
        self.add_transition('set_system_prompt', 'idle', 'awaiting_system_prompt')
        self.add_transition('set_temperature', 'idle', 'awaiting_temperature')
        self.add_transition('set_top_p', 'idle', 'awaiting_top_p')
        self.add_transition('set_max_tokens', 'idle', 'awaiting_max_tokens')
        
        # Define a transition to return to idle state from any other state
        self.add_transition('return_to_idle', '*', 'idle')