def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)


def superf_pickover(n):
    fact = factorial(n)
    res = fact
    for _ in range(fact):
        res = res ** fact
    return res


def ex_factorial(n):
    temp = n - 1
    stepen = temp
    while temp != 1:
        temp -= 1
        stepen = stepen ** temp
    return n ** stepen


def hyper_factorial(n):
    if n == 0:
        return 1
    return (n ** n) * hyper_factorial(n - 1)


print(factorial(5))
print(superf_pickover(2))
print(ex_factorial(4))
print(hyper_factorial(4))
