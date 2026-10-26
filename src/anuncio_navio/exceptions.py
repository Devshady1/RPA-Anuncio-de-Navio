class AnuncioError(Exception):
    pass


class LoginError(AnuncioError):
    pass


class LookupError(AnuncioError):
    pass


class VerificacaoError(AnuncioError):
    pass


class AnuncioEmAndamentoError(AnuncioError):
    pass
