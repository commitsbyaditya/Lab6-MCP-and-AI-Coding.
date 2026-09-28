"""
Student Marks Management System

Stores student names and marks, and shows:
  - the class average
  - the topper
  - the students who scored below 40
"""

PASS_MARK = 40  # marks below this count as "below 40"


def add_student(students, name, marks):
    """Add a student, or update their marks if the name already exists.

    Args:
        students (dict): Student name -> marks.
        name (str): The student's name.
        marks (float): Marks between 0 and 100.
    """
    if not 0 <= marks <= 100:
        print(f"Skipped {name}: marks must be between 0 and 100.")
        return
    students[name] = marks


def calculate_average(students):
    """Return the average marks, or 0 if there are no students."""
    if not students:
        return 0
    return sum(students.values()) / len(students)


def find_topper(students):
    """Return (name, marks) of the highest scorer, or (None, None) if empty."""
    if not students:
        return None, None
    # key=students.get tells max() to compare marks instead of names
    topper = max(students, key=students.get)
    return topper, students[topper]


def students_below_pass(students):
    """Return a list of (name, marks) for students below PASS_MARK."""
    return [(name, marks) for name, marks in students.items() if marks < PASS_MARK]


def print_report(students):
    """Print every student followed by the class summary."""
    print("----- Student Marks -----")
    for name, marks in students.items():
        print(f"{name:<10} {marks}")

    print(f"\nClass average : {calculate_average(students):.2f}")

    topper, top_marks = find_topper(students)
    print(f"Topper        : {topper} ({top_marks})")

    below = students_below_pass(students)
    print(f"Below {PASS_MARK}      : ", end="")
    print(", ".join(f"{n} ({m})" for n, m in below) if below else "None")


def main():
    """Create the class list, add some students and print the report."""
    students = {}

    # Sample data. Replace it with input() calls to type marks in yourself.
    add_student(students, "Asha", 85)
    add_student(students, "Rahul", 38)
    add_student(students, "Meena", 92)
    add_student(students, "Kiran", 25)
    add_student(students, "Vikram", 71)
    add_student(students, "Divya", 105)  # invalid, gets skipped

    print_report(students)


if __name__ == "__main__":
    main()
