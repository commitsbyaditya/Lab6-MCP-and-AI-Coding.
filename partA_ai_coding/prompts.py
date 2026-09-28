"""The five Exp 6 prompts, copied from the CS3235 lab manual.

The same text is sent to every AI tool, so the answers can be compared fairly.
"""

FAULTY_CODE = '''def average_marks(marks):
    total = 0
    for mark in marks:
        total = total + mark
    return total / len(marks)

students = {
    "Asha": 85,
    "Rahul": 72,
    "Meena": 38
}

avg = average_marks(students)
print("Average marks:", avg)'''

ORIGINAL_CODE = '''students = {
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
        print(s, "has failed")'''

UNDOCUMENTED_CODE = '''def calculate_average(student_marks):
    return sum(student_marks.values()) / len(student_marks)

def get_topper(student_marks):
    topper = max(student_marks, key=student_marks.get)
    return topper, student_marks[topper]

def get_failed_students(student_marks):
    return [
        student
        for student, marks in student_marks.items()
        if marks < 40
    ]'''

PROMPTS = {
    "subtask1": """Write a Python program for a student marks management system.
Requirements:
1. Store student names and marks.
2. Calculate the class average.
3. Display the topper.
4. Display students who scored below 40.
5. Use functions.
6. Keep the code simple for undergraduate students.""",

    "subtask2": "The following Python code is giving an error. Please debug it, explain the "
                "mistake, and provide corrected code.\n\n" + FAULTY_CODE,

    "subtask3": """Refactor the following Python code.
Goals:
1. Improve readability.
2. Use functions.
3. Use meaningful variable names.
4. Avoid repeated logic.
5. Keep it simple for undergraduate students.

""" + ORIGINAL_CODE,

    "subtask4": """Add clear documentation to the following Python code.
Include:
1. Function-level docstrings.
2. Simple inline comments.
3. A short README-style explanation.
4. Keep the explanation suitable for undergraduate students.

""" + UNDOCUMENTED_CODE,

    "subtask5": """Create a Python program for a student marks management system.
The program should:
1. Store student names and marks.
2. Calculate average marks.
3. Find the topper.
4. List students below 40.
5. Use functions.
6. Add comments and docstrings.
7. Keep the code beginner-friendly.""",
}
