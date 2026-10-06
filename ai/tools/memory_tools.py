from ..logger import get_logger


logger = get_logger("atlas.memory_tool")


def buscar_memoria(memory, query):
    logger.info(
        "Busca memória | query=%r",
        query
    )

    if not query or not query.strip():
        logger.info(
            "Busca memória ignorada | query vazia"
        )
        return []

    result = memory.search_memory(
        query.strip()
    )

    if result is None:
        result = []

    logger.info(
        "Busca memória concluída | resultados=%s",
        len(result)
    )

    logger.debug(
        "Busca memória retorno | %r",
        result
    )

    return result