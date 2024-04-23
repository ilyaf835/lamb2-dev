from pydantic import BaseModel


class BotInfo(BaseModel):
    user_name: str
    bot_name: str
    room_url: str
    hidden: bool = False
