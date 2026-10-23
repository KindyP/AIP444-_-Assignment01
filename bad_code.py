import sys
import math
from typing import List

def calculate_total(prices: List[float]) -> int:
    x = 0.0
    for p in prices:
        x += p
    return x

def main():
    api_key = "sk-12345-abcde-secret-key"
    print(f"Value of pi is: {math.pi}")
    total = calculate_total([10.50, 20.00, 5.25])
    print(f"Total: {total}")

if __name__ == "__main__":
    main()