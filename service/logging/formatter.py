import json
import logging


class JSONFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        message = {
            'level': record.levelname,
            'message': record.getMessage(),
            'timestamp': record.created,
            'traceback': self.formatException(record.exc_info) if record.exc_info else None}

        return json.dumps(message)
