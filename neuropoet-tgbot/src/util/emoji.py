from enum import Enum
from dataclasses import dataclass
from typing import Type, Any


@dataclass(frozen=True)
class EmojiEntry:
    emoji: str
    reaction_supported: bool = False


class EmojiTypeMeta(type(Enum)):
    """Metaclass to enforce EmojiEntry values"""

    def __new__(cls, clsname: str, bases: tuple, namespace: dict) -> Type[Enum]:
        # Create the enum class
        enum_cls = super().__new__(cls, clsname, bases, namespace)

        # Validate all member values
        for member in enum_cls:
            if not isinstance(member.value, EmojiEntry):
                raise TypeError(
                    f"Enum member {member.name} must have EmojiEntry instance as value"
                )
        return enum_cls


class Emoji(Enum, metaclass=EmojiTypeMeta):
    """Enum where all values are EmojiEntry instances"""
    CHECK_MARK = EmojiEntry('✅')
    WARNING = EmojiEntry('⚠️')
    CROSSOUT = EmojiEntry('❌')
    HOURGLASS = EmojiEntry('⏳')
    THUMBS_UP = EmojiEntry('👍', reaction_supported=True)
    THUMBS_DOWN = EmojiEntry('👎', reaction_supported=True)
    THINK = EmojiEntry('🤔', reaction_supported=True)
    BIG_SMILE = EmojiEntry('😁', reaction_supported=True)
    TEAR = EmojiEntry('😢', reaction_supported=True)
    FEAR = EmojiEntry('😱', reaction_supported=True)
    SURPRISE = EmojiEntry('🤯', reaction_supported=True)
    DISGUST = EmojiEntry('🤮', reaction_supported=True)
    ANGER = EmojiEntry('😡', reaction_supported=True)
    NEUTRAL = EmojiEntry('😐', reaction_supported=True)

    @property
    def emoji(self) -> str:
        """Direct access to emoji string"""
        return self.value.emoji

    @classmethod
    def from_emoji(cls, emoji_str: str) -> 'Emoji':
        """Get enum member by emoji string"""
        for member in cls:
            if member.value.emoji == emoji_str:
                return member
        raise ValueError(f"No Emoji found for '{emoji_str}'")