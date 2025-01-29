import logging


std_formatter = logging.Formatter(
    "{time:\"%(asctime)s\","
    "level:\"%(levelname)s\","
    "filename:\"%(filename)s\","
    "function:\"%(funcName)s\"," 
    "lineno:%(lineno)d,"
    "msg:\"%(message)s\"}"
)


def get_logger():
    logger: logging.Logger | None = None

    def _get_logger():
        nonlocal logger

        if logger != None:
            return logger

        logger = logging.getLogger()

        logger.setLevel(logging.INFO)
        
        file_handler = logging.FileHandler("log.txt")
        file_handler.setFormatter(std_formatter)
        logger.addHandler(file_handler)

        # stream_handler = logging.StreamHandler()
        # stream_handler.setFormatter(std_formatter)
        # logger.addHandler(stream_handler)

        return logger

    return _get_logger


logger = get_logger()()
