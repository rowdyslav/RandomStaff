from random import choice
from emoji import EMOJI_DATA

EMOJIS = list(EMOJI_DATA)


def space_to_emoji(text):
    return (choice(EMOJIS) if x == " " else x for x in text)


def pasta_print(text):
    a, b = choice(EMOJIS), choice(EMOJIS)
    print(a + "".join(space_to_emoji(text)) + b)


old = None
while True:
    new = input().replace("  ", " ").strip()
    if not new:  # Нажат Enter = Выводим старый базовый текст
        if old:
            pasta_print(old)
        else:
            print("Нету никакого текста для обработки!")
    elif len(new) == 1:  # Инпут из одного символа = Выход
        print("Выход из программы")
        break
    else:
        pasta_print(new)  # Инпут больше одного символа = Выводим новый базовый текст
        old = new
