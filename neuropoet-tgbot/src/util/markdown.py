def escape_markdown(text: str) -> str:
    """
    Escapes special characters for Telegram's MarkdownV2 syntax.
    Handles None gracefully.
    """
    if text is None:
        return ""

    # All special characters for MarkdownV2 per Telegram docs
    escape_chars = {'_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!', '\\'}

    return ''.join(
        f'\\{char}' if char in escape_chars else char
        for char in text
    )