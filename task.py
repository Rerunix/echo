# A small program with a hidden bug.
# It is supposed to ADD two numbers and print the total.
# The correct answer is 8.

a = 3
b = 5

print("step 1: read numbers %d and %d" % (a, b))

total = a - b   # <-- the bug hides here (it should be a + b)

print("step 2: compute total -> %d" % total)
print("step 3: final answer -> %d" % total)
