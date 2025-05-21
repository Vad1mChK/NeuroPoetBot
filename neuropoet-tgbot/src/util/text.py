def truncate_text(
        s: str,
        total_limit: int | None = 256,
        vert_limit: int | None = 4,
        ellipsis: str = "..."
) -> str:
    """
    Truncate text explicitly based on total character limit or line count.

    Parameters:
        s (str): Input text.
        total_limit (int | None): Maximum allowed total characters. None disables limit.
        vert_limit (int | None): Maximum allowed lines. None disables limit.
        ellipsis (str): String to append if truncation occurs.

    Returns:
        str: Truncated text with ellipsis if needed.
    """
    lines = s.splitlines()
    truncated = False

    if vert_limit is not None and len(lines) > vert_limit:
        lines = lines[:vert_limit]
        truncated = True

    result = "\n".join(lines)

    if total_limit is not None and len(result) > total_limit:
        result = result[:total_limit].rstrip()
        truncated = True

    if truncated:
        result += ellipsis

    return result
