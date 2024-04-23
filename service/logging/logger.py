import logging
import logging.config


config = {
    "version": 1,
    "formatters": {
        "json": {
            "()": "service.logging.formatter.JSONFormatter"}
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "json",
            "stream": "ext://sys.stdout"},
    },
    "root": {
        "level": "INFO",
        "handlers": ["stdout"]
    }
}


logging.config.dictConfig(config)
logger = logging.getLogger('service')
