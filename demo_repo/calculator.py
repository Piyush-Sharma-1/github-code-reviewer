"""Calculator module with basic arithmetic functions"""
def divide(a, b):
    """Divide two numbers"""
    return a / b

def calculate_average(numbers):
    """Calculate the average of a list of numbers"""
    total = 0
    for n in numbers:
        total = total + n
    return total / len(numbers)

def is_even(n):
    """Check if a number is even"""
    return n % 2 == 0
