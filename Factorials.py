def f(n: int) -> int:
    if n < 0:
        raise ValueError("n должно быть >= 0")
    if n == 0:
        return 1
    return n * f(n - 1)


def super_f_pickover(n: int) -> int:
    fact = f(n)
    res = fact
    for _ in range(fact):
        res = res ** fact
    return res


def ex_f(n: int) -> int:
    if n < 0:
        raise ValueError("n должно быть >= 0")
    if n in (0, 1):
        return 1

    temp = n - 1
    stepen = temp
    while temp > 1:
        temp -= 1
        stepen = stepen ** temp
    return n ** stepen


def hyper_f(n: int) -> int:
    if n < 0:
        raise ValueError("n должно быть >= 0")
    if n == 0:
        return 1
    return (n ** n) * hyper_f(n - 1)


def format_value(value: int, width: int, plain_max: int = 12) -> str:
    text = str(value)
    if len(text) <= plain_max:
        return text

    digits = str(len(text))
    suffix = f" ({digits} цифр)"
    budget = width - len(suffix)

    if budget <= 3:
        return f"{len(text)} цифр"

    body_budget = budget - 3
    head = max(2, body_budget // 2)
    tail = max(2, body_budget - head)
    return f"{text[:head]}...{text[-tail:]}{suffix}"


def fit(text: str, width: int) -> str:
    if len(text) > width:
        if width <= 3:
            return text[:width]
        return text[:width - 3] + "..."
    return text.ljust(width)


TOO_LARGE = ">=4301 цифр"

def _super(n: int) -> str:
    if n > 2:
        return TOO_LARGE
    return format_value(super_f_pickover(n), 20)


def _ex(n: int) -> str:
    if n > 5:
        return TOO_LARGE
    return format_value(ex_f(n), 20)


def main() -> None:
    headers = (
        ("n", 2),
        ("f", 18),
        ("hyper", 24),
        ("ex", 20),
        ("super pickover", 20),
    )
    header_line = " | ".join(name.ljust(width) for name, width in headers)
    sep_line = "-+-".join("-" * width for _, width in headers)
    print(header_line)
    print(sep_line)

    for n in range(10):
        row = [
            fit(str(n), 2),
            fit(format_value(f(n), 18), 18),
            fit(format_value(hyper_f(n), 24), 24),
            fit(_ex(n), 20),
            fit(_super(n), 20),
        ]
        print(" | ".join(row))


if __name__ == "__main__":
    main()
