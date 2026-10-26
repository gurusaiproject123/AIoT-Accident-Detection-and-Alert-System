def add_numbers(first_number: float, second_number: float) -> float:
    return first_number + second_number


if __name__ == "__main__":
    first_number = float(input("Enter the first number: "))
    second_number = float(input("Enter the second number: "))
    result = add_numbers(first_number, second_number)
    print(f"The sum is: {result}")
