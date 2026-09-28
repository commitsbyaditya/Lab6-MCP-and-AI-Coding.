"""
Student marks helper functions.

This module contains three small utilities that work with a dictionary
mapping student names to their numeric marks.

Functions
---------
calculate_average(student_marks)
    Return the average mark of all students.

get_topper(student_marks)
    Return the name of the student with the highest mark and that mark.

get_failed_students(student_marks)
    Return a list of students whose mark is below 40.
"""

def calculate_average(student_marks):
    """
    Compute the average mark of all students.

    Parameters
    ----------
    student_marks : dict
        Keys are student names (strings), values are marks (int or float).

    Returns
    -------
    float
        The arithmetic mean of the marks.
    """
    # Sum all marks and divide by the number of students
    return sum(student_marks.values()) / len(student_marks)


def get_topper(student_marks):
    """
    Find the student with the highest mark.

    Parameters
    ----------
    student_marks : dict
        Mapping of student names to marks.

    Returns
    -------
    tuple
        (topper_name, topper_mark)
    """
    # max() with key=student_marks.get returns the key with the largest value
    topper = max(student_marks, key=student_marks.get)
    return topper, student_marks[topper]


def get_failed_students(student_marks):
    """
    List all students who scored below 40.

    Parameters
    ----------
    student_marks : dict
        Mapping of student names to marks.

    Returns
    -------
    list
        Names of students whose mark is less than 40.
    """
    # List comprehension filters students with marks < 40
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
help(calculate_average)
