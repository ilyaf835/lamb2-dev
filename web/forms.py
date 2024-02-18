from pydantic import BaseModel, field_validator


class IndexForm(BaseModel):
    user_name: str
    bot_name: str
    room_url: str
    hidden: bool

    @field_validator('user_name', 'bot_name', 'room_url', 'hidden', mode='before')
    @classmethod
    def extract_field(cls, fields: list):
        if not isinstance(fields, list):
            raise ValueError('Field must be a list')
        return fields[0]
