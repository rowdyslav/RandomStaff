import random

def take_stones(player):
    if player == "Обезьянка":
        hod_obez = STONES % (LIMIT + 1) if STONES % (LIMIT + 1) != 0 else random.randint(1, LIMIT)
        STONES -= hod_obez
        print(f'{player} взяла {hod_obez} камней, осталось {STONES}')
    else:
        hod_user = int(input())
        while hod_user > LIMIT or hod_user > STONES or hod_user <= 0:
            print(f'Некорректный ход: {hod_user}')
            hod_user = int(input())
        STONES -= hod_user
        print(f'Вы взяли {hod_user} камней, осталось {STONES}')
    return STONES

def main():
    global STONES, LIMIT

    STONES = int(input('Сколько камней в куче? '))
    LIMIT = int(input('Какой максимум камней можно взять за ход? '))

    while True:
        STONES = take_stones(STONES, LIMIT)
        if STONES == 0:
            print('Обезьянка выиграла!')
            break
        
        STONES = take_stones(STONES, LIMIT)
        if STONES == 0:
            print('Вы выиграли обезьянку!')
            break

main()
