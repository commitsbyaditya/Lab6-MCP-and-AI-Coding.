Below is the same code, now annotated with clear, beginner‑friendly documentation.  
Feel free to copy it into your own project or use it as a teaching example.

```python
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
```

---

## README‑style explanation (for undergraduates)

**What this module does**

- **`calculate_average`**: Takes a dictionary of student names → marks and returns the average mark.
- **`get_topper`**: Finds the student with the highest mark and returns both the name and the mark.
- **`get_failed_students`**: Returns a list of all students who scored below 40 (the typical passing threshold).

**How to use it**

```python
marks = {
    "Alice": 78,
    "Bob": 35,
    "Charlie": 92,
    "Diana": 41
}

print(calculate_average(marks))          # → 64.5
print(get_topper(marks))                 # → ('Charlie', 92)
print(get_failed_students(marks))        # → ['Bob']
```

**Why the documentation matters**

- Function docstrings explain *what* each function does, its inputs, and its output.  
- Inline comments show the key steps inside the functions, making the logic easy to follow.  
- The README‑style section gives a quick, high‑level overview that anyone can read without diving into the code.

Feel free to extend these utilities or adapt them for your own projects!