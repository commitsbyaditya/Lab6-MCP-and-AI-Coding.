def calculate_average(student_marks):
    return sum(student_marks.values()) / len(student_marks)

def get_topper(student_marks):
    topper = max(student_marks, key=student_marks.get)
    return topper, student_marks[topper]

def get_failed_students(student_marks):
    return [
        student
        for student, marks in student_marks.items()
        if marks < 40
    ]

marks = {"Asha": 85, "Rahul": 72, "Meena": 38, "Vikram": 91}
print("calculate_average ->", calculate_average(marks))
print("get_topper        ->", get_topper(marks))
print("get_failed_students ->", get_failed_students(marks))
print()

