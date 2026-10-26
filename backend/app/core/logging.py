import logging
import sys


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    groq_logger = logging.getLogger("openai")
    groq_logger.setLevel(logging.WARNING)

    openai_logger = logging.getLogger("openai")
    openai_logger.setLevel(logging.WARNING)
