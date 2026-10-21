import time
import functools
import logging

logger = logging.getLogger("anuncio.retry")


def com_retry(tentativas=3, backoff_base=2.0, excecoes=(Exception,)):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            ultimo = None
            for t in range(1, tentativas + 1):
                try:
                    return fn(*a, **kw)
                except excecoes as e:
                    ultimo = e
                    logger.warning(f"Tentativa {t}/{tentativas} falhou em {fn.__name__}: {e}")
                    if t < tentativas:
                        time.sleep(backoff_base * t)
            raise ultimo
        return wrapper
    return deco
