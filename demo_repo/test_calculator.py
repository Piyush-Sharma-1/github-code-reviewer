from calculator import divide, calculate_average, is_even


def test_divide():
    assert divide(10, 2) == 5


def test_calculate_average():
    assert calculate_average([1, 2, 3, 4, 5]) == 3


def test_is_even():
    assert is_even(4) is True
    assert is_even(3) is False