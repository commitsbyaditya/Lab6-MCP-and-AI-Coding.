# Student Marks Management System

def read_students():
    """Ask how many students there are, then read each name and mark."""
    students = {}
    count = int(input("Enter number of students: "))
    for i in range(count):
        name = input(f"Name of student {i + 1}: ")
        marks = float(input(f"Marks of {name}: "))
        students[name] = marks
    return students


def calculate_average(students):
    """Return the class average."""
    return sum(students.values()) / len(students)


def find_topper(students):
    """Return the name and marks of the student with the highest marks."""
    topper = max(students, key=students.get)
    return topper, students[topper]


def students_below_40(students):
    """Return a list of names of students who scored below 40."""
    return [name for name, marks in students.items() if marks < 40]


def main():
    students = read_students()

    print("\nClass Average:", round(calculate_average(students), 2))

    topper, top_marks = find_topper(students)
    print("Topper:", topper, "with", top_marks, "marks")

    below = students_below_40(students)
    if below:
        print("Students below 40:", ", ".join(below))
    else:
        print("No student scored below 40.")


main()
