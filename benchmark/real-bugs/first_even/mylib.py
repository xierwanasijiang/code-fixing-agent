def first_even(nums):
    for n in nums:
        if n % 2 == 0:
            return n
    return 0
