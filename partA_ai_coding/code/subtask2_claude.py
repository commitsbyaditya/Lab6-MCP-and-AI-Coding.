def average_marks(marks):
    total = 0
    for mark in marks.values():   # loop over the marks, not the names
        total = total + mark
    return total / len(marks)


students = {
    "Asha": 85,
    "Rahul": 72,
    "Meena": 38
}

avg = average_marks(students)
print("Average marks:", avg)
