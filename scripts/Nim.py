from random import randint

MON_NAME = "Обезьянка"


def read_positive_int(prompt: str) -> int:
    while True:
        try:
            value = int(input(prompt))
        except ValueError:
            print("Введите целое число")
            continue
        if value <= 0:
            print("Число должно быть больше 0")
            continue
        return value


def take_stones(is_mon: bool = False) -> None:
    global LIMIT, stones

    if is_mon:
        move_mon = (
            stones % (LIMIT + 1)
            if stones % (LIMIT + 1) != 0
            else randint(1, LIMIT)
        )
        stones -= move_mon
        print(f"{MON_NAME} взяла {move_mon} камней, осталось {stones}")
    else:
        while True:
            try:
                move_user = int(input())
            except ValueError:
                print("Введите целое число")
                continue
            if move_user > LIMIT or move_user > stones or move_user <= 0:
                print(f"Некорректный ход: {move_user}")
                continue
            break
        stones -= move_user
        print(f"Вы взяли {move_user} камней, осталось {stones}")


def main() -> None:
    global stones, LIMIT

    stones = read_positive_int("Сколько камней в куче? > ")
    LIMIT = min(read_positive_int("Какой максимум камней можно взять за ход? > "), stones)

    while True:
        take_stones(is_mon=True)
        if stones == 0:
            print(f"{MON_NAME} выиграла!")
            break

        take_stones()
        if stones == 0:
            print("Вы выиграли обезьянку!")
            break


if __name__ == "__main__":
    main()
