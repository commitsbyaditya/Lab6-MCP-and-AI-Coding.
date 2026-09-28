"""Helper functions for a student marks management system.

Marks are stored in a dictionary where the key is the student's name
and the value is their marks, for example {"Asha": 85, "Meena": 38}.
"""

PASS_MARK = 40  # students scoring below this are counted as failed


def calculate_average(student_marks):
    """Calculate the class average.

    Args:
        student_marks (dict): Student name -> marks.

    Returns:
        float: The average of all the marks.
    """
    # Add up every mark, then divide by how many students there are
    return sum(student_marks.values()) / len(student_marks)


def get_topper(student_marks):
    """Find the student with the highest marks.

    Args:
        student_marks (dict): Student name -> marks.

    Returns:
        tuple: (name, marks) of the topper.
    """
    # key=student_marks.get makes max() compare the marks, not the names
    topper = max(student_marks, key=student_marks.get)
    return topper, student_marks[topper]


def get_failed_students(student_marks):
    """List the students who scored below the pass mark.

    Args:
        student_marks (dict): Student name -> marks.

    Returns:
        list: Names of students with marks below PASS_MARK.
    """
    # Keep only the students whose marks are under the pass mark
    return [
        student
        for student, marks in student_marks.items()
        if marks < PASS_MARK
    ]

marks = {"Asha": 85, "Rahul": 72, "Meena": 38, "Vikram": 91}
print("calculate_average ->", calculate_average(marks))
print("get_topper        ->", get_topper(marks))
print("get_failed_students ->", get_failed_students(marks))
print()
help(calculate_average)
