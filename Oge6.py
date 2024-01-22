from typing import Tuple

vvod1 = input().strip().replace(';', ',')
vvod2 = input().strip()
vvod3 = int(input("Количество нет > "))


numbers: Tuple[int, int]
= (0, 0)
exec(f"numbers = {vvod1 + vvod2}")

key = lambda x: x[0]
mn = min(numbers, key=key)[0]
mx = max(numbers, key=key)[0]

for A in range (len(numbers)):
    no_count = 0
    for s, t in numbers:
        if not (A > s and t < 5):
            no_count += 1
if no_count == vvod3:
    print (A)
