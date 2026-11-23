"""Use the operating system's trusted CAs without disabling TLS verification."""


def configure_tls():
    import truststore
    # Run in the application worker before requests, urllib3 or model imports.
    truststore.inject_into_ssl()


def error_message(error, token=""):
    message = str(error)
    if "CERTIFICATE_VERIFY_FAILED" in message or "SSLCertVerificationError" in message:
        return (
            "Не удалось проверить HTTPS-сертификат сервера загрузки моделей. "
            "Это ошибка защищённого соединения, а не проверка Hugging Face token. "
            "Возможная причина — корпоративный прокси или антивирус с проверкой HTTPS. "
            "Убедитесь, что корневой сертификат вашей организации установлен в доверенное "
            "хранилище Windows; при необходимости обратитесь к администратору. "
            "После настройки остановите очередь и добавьте запись заново."
        )
    return message.replace(token, "[token]")[-1600:] if token else message[-1600:]
