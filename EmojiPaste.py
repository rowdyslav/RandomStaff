from random import choice
from typing import Iterator

from emoji import EMOJI_DATA

EMOJIS: list[str] = list(EMOJI_DATA)


def space_to_emoji(text: str) -> Iterator[str]:
    return (choice(EMOJIS) if x == " " else x for x in text)


def pasta_print(text: str) -> None:
    a, b = choice(EMOJIS), choice(EMOJIS)
    print(a + "".join(space_to_emoji(text)) + b)


def main() -> None:
    old: str | None = None
    while True:
        new = input().replace("  ", " ").strip()
        if not new:  # Нажат Enter = Выводим старый базовый текст
            if old is not None:
                pasta_print(old)
            else:
                print("Нету никакого текста для обработки!")
        elif len(new) == 1:  # Инпут из одного символа = Выходим
            print("Выход из программы")
            break
        else:
            pasta_print(new)  # Инпут больше одного символа = Выводим новый базовый текст
            old = new


if __name__ == "__main__":
    main()
