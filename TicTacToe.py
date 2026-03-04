BOARD: list[list[str]] = [['1', '2', '3'],
                          ['4', '5', '6'],
                          ['7', '8', '9']]


def print_board() -> None:
    for row in BOARD:
        print(' | '.join(row))


def ask_symbol(prompt: str, used: set[str] | None = None) -> str:
    used = used or set()
    while True:
        symb = input(prompt).strip()
        if len(symb) != 1:
            print("Символ должен быть длиной 1")
            continue
        if symb.isdigit():
            print("Нельзя использовать цифры 1-9")
            continue
        if symb in used:
            print("Этот символ уже занят")
            continue
        return symb


def move(pos: int, symb: str) -> bool:
    if pos < 1 or pos > 9:
        print("Позиция должна быть от 1 до 9")
        return False

    row = (pos - 1) // 3
    col = (pos - 1) % 3

    if not BOARD[row][col].isdigit():
        print("Клетка уже занята")
        return False

    BOARD[row][col] = symb
    return True


def check_win(symb: str) -> bool:
    for i in range(3):
        if BOARD[i] == [symb] * 3:
            print(symb, 'победил!')
            return True
        if BOARD[0][i] == BOARD[1][i] == BOARD[2][i] == symb:
            print(symb, 'победил!')
            return True

    if BOARD[0][0] == BOARD[1][1] == BOARD[2][2] == symb:
        print(symb, 'победил!')
        return True
    if BOARD[2][0] == BOARD[1][1] == BOARD[0][2] == symb:
        print(symb, 'победил!')
        return True

    return False


def check_draw() -> bool:
    for row in BOARD:
        for cell in row:
            if cell.isdigit():
                return False
    print('Draw!')
    return True


def ask_move(symb: str) -> None:
    while True:
        print('Куда ставишь', symb + '?')
        try:
            pos = int(input())
        except ValueError:
            print("Введите целое число")
            continue
        if move(pos, symb):
            return


def main() -> None:
    first = ask_symbol('Кто ходит первым? ')
    second = ask_symbol('Кто вторым? ', {first})

    print_board()
    while True:
        for p in first, second:
            ask_move(p)
            print_board()
            if check_win(p) or check_draw():
                break


if __name__ == "__main__":
    main()
