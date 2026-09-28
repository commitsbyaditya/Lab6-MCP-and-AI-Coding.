students = {
    "Asha": 85,
    "Rahul": 72,
    "Meena": 38,
    "Vikram": 91
}

total = 0
for s in students:
    total = total + students[s]
avg = total / len(students)
print("Average:", avg)

top = ""
top_marks = 0
for s in students:
    if students[s] > top_marks:
        top = s
        top_marks = students[s]
print("Topper:", top)

for s in students:
    if students[s] < 40:
        print(s, "has failed")
