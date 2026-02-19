'''
Functionality for example namespace:

import template

ns = template.item_1()
'''
from __future__ import annotations
from typing import TYPE_CHECKING


# Public, supported “namespaces”.
__all__ = ("item_1", "item_2")


# Helps IDEs/type-checkers know these exist and what they are,
# without importing them at runtime.
if TYPE_CHECKING:
    from .item_folder.item_1_file import item_1
    from .item_folder.item_2_file import item_2


def __getattr__(name: str):
    if name == 'item_1':
        from .item_folder.item_1_file import item_1
        globals()[name] = item_1  # Recommended for smoother checking.
        return item_1

    if name == 'item_2':
        from .item_folder.item_2_file import item_2
        globals()[name] = item_2  # Recommended for smoother checking.
        return item_2

    raise AttributeError(f'Module "<lib name>" has no attribute {name!r}!')  # TODO: Edit your library name.


def __dir__() -> list[str]:
    # Makes dir(llm) include your lazy “namespaces”.
    return sorted(set(globals().keys()) | set(__all__))