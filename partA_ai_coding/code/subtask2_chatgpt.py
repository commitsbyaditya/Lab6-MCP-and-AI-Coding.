def average_marks(marks):
    """Return the arithmetic mean of a collection of numbers."""
    # Guard against an empty collection
    if not marks:
        return 0  # or raise ValueError("No marks to average")

    total = 0
    for mark in marks:
        total += mark
    return total / len(marks)


students = {
    "Asha": 85,
    "Rahul": 72,
    "Meena": 38
}

# Pass the numeric values, not the keys
avg = average_marks(students.values())
print("Average marks:", avg)   # → Average marks: 65.0
