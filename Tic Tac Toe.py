def hoddd(hod, symb, poss):
    if hod < 4:
        poss[0][hod - 1] = symb
    elif hod < 7:
        poss[1][hod - 1 - 3] = symb
    elif hod < 10:
        poss[2][hod - 1 - 6] = symb

def check_win(symb, poss):
    for check in range(len(poss)):
        wins = [
            poss[check] == [symb] * 3,
            poss[0][check] == poss[1][check] == poss[2][check],
            poss[0][0] == poss[1][1] == poss[2][2] or poss[2][0] == poss[1][1] == poss[0][2]
        ]
        if any(wins):
            print(symb, 'победил!')
            return True
    return False

def check_draw(poss):
    for check in range(len(poss)):
        if poss[check] != first and poss[check] != second:
            return
    print('Draw!')
    return True

poss = [['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9']]
End = False
print('Кто ходит первым?')
first = input()
print('Кто вторым?')
second = input()
for i in poss:
    print(' | '.join(i))
while not End:
    print('Куда ставишь', first + '?')
    hoddd(int(input()), first, poss)
    for i in poss:
        print(' | '.join(i))
    if check_win(first, poss) or check_draw(poss):
        break
    print('Куда ставишь', second + '?')
    hoddd(int(input()), second, poss)
    for i in poss:
        print(' | '.join(i))
    if check_win(second, poss) or check_draw(poss):
        break