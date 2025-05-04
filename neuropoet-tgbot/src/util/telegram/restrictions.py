import os
from typing import Callable, Any, Coroutine
from aiogram import types
from aiogram.dispatcher import dispatcher
from functools import wraps
from dotenv import load_dotenv


def get_owner_ids() -> list[int]:
    '''
    Obtains a list of bot owners, parsed from the env_variable `NPB_OWNER_USER_IDS`,

    Expects the env variable to be a list of integers, separated by comma wihout spaces, e.g.

    `NPB_OWNER_USER_IDS=123456789,123456790`
    :return: List of bot owner IDs, or an empty list if unable to parse the variable.
    '''
    owner_ids_line = os.getenv('NPB_OWNER_USER_IDS', '').strip()
    if not owner_ids_line:
        return []

    return [
        int(clean_id)
        for owner_id in owner_ids_line.split(',')
        if (clean_id := owner_id.strip()).isdigit()
    ]


def owner_only_command(
        default_action: Callable[[types.Message], Coroutine[Any, Any, None]],
        owner_ids_provider: Callable[[], list[int]] = get_owner_ids
) -> Callable:
    """
    Decorator that restricts command access to bot owners only.

    Args:
        default_action: Async function to execute for non-owner users
        owner_ids_provider: Function that returns list of owner IDs
                           (default: get_owner_ids)

    Returns:
        Command handler wrapped with ownership check

    Usage:
        @dp.message_handler(commands['admin'])
        @owner_only_command(default_permission_denied)
        async def admin_command(message: types.Message):
            # Owner-only logic here
    """

    def decorator(handler: Callable[[types.Message], Coroutine[Any, Any, None]]):
        @wraps(handler)
        async def wrapped(message: types.Message, *args, **kwargs):
            # Get fresh list of owner IDs on each call
            authorized_ids = owner_ids_provider()

            if message.from_user.id in authorized_ids:
                return await handler(message, *args, **kwargs)
            return await default_action(message, *args, **kwargs)

        return wrapped

    return decorator


if __name__ == '__main__':
    load_dotenv()
    print(f'Owners: {get_owner_ids()}')
