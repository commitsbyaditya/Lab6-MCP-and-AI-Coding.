PASS_MARK = 40


def calculate_average(student_marks):
    """Return the average marks of the class."""
    return sum(student_marks.values()) / len(student_marks)


def get_topper(student_marks):
    """Return the name and marks of the highest scorer."""
    topper = max(student_marks, key=student_marks.get)
    return topper, student_marks[topper]


def get_failed_students(student_marks):
    """Return the names of students who scored below the pass mark."""
    return [name for name, marks in student_marks.items() if marks < PASS_MARK]


def main():
    student_marks = {
        "Asha": 85,
        "Rahul": 72,
        "Meena": 38,
        "Vikram": 91
    }

    print("Average:", calculate_average(student_marks))

    topper, topper_marks = get_topper(student_marks)
    print("Topper:", topper, "with", topper_marks, "marks")

    for name in get_failed_students(student_marks):
        print(name, "has failed")


main()
