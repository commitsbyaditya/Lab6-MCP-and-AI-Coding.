Below is a **single‑file** Python script that implements a very small “Student Marks Management System”.  
Everything is wrapped in functions, each function has a short docstring, and the code is heavily commented so a beginner can follow along.

```python
#!/usr/bin/env python3
"""
Student Marks Management System

This script lets you:
    • Add a student name and a mark
    • Compute the average mark of all students
    • Find the student with the highest mark (the topper)
    • List all students whose mark is below 40

The data is kept in a simple list of dictionaries – no external files or databases are needed.
"""

# --------------------------------------------------------------------------- #
# 1.  Data storage
# --------------------------------------------------------------------------- #
# We keep the data in a list called `students`.  Each element is a dictionary
# with two keys: 'name' and 'mark'.
students = []


# --------------------------------------------------------------------------- #
# 2.  Helper functions
# --------------------------------------------------------------------------- #
def add_student(name: str, mark: float) -> None:
    """
    Add a new student to the system.

    Parameters
    ----------
    name : str
        The student's name.
    mark : float
        The student's mark (0–100).
    """
    # Basic validation – keep the example simple
    if not (0 <= mark <= 100):
        print("Mark must be between 0 and 100. Student not added.")
        return

    # Append a new dictionary to the list
    students.append({"name": name, "mark": mark})
    print(f"Added {name} with mark {mark}.")


def calculate_average() -> float:
    """
    Compute the average mark of all students.

    Returns
    -------
    float
        The average mark, or 0.0 if there are no students.
    """
    if not students:
        return 0.0

    total = sum(student["mark"] for student in students)
    return total / len(students)


def find_topper() -> tuple | None:
    """
    Find the student with the highest mark.

    Returns
    -------
    tuple or None
        (name, mark) of the topper, or None if there are no students.
    """
    if not students:
        return None

    topper = max(students, key=lambda s: s["mark"])
    return topper["name"], topper["mark"]


def list_below_threshold(threshold: float = 40.0) -> list:
    """
    Return a list of students whose marks are below the given threshold.

    Parameters
    ----------
    threshold : float, optional
        The cut‑off mark. Defaults to 40.0.

    Returns
    -------
    list
        A list of (name, mark) tuples for students below the threshold.
    """
    return [(s["name"], s["mark"]) for s in students if s["mark"] < threshold]


# --------------------------------------------------------------------------- #
# 3.  Simple text menu (optional)
# --------------------------------------------------------------------------- #
def show_menu() -> None:
    """Print the menu options."""
    print("\n--- Student Marks Management System ---")
    print("1. Add a student")
    print("2. Show average mark")
    print("3. Show topper")
    print("4. List students below 40")
    print("5. Exit")


def main() -> None:
    """Main loop of the program."""
    while True:
        show_menu()
        choice = input("Enter your choice (1‑5): ").strip()

        if choice == "1":
            name = input("Student name: ").strip()
            try:
                mark = float(input("Mark (0‑100): ").strip())
            except ValueError:
                print("Invalid mark – please enter a number.")
                continue
            add_student(name, mark)

        elif choice == "2":
            avg = calculate_average()
            print(f"Average mark: {avg:.2f}")

        elif choice == "3":
            topper = find_topper()
            if topper:
                print(f"Topper: {topper[0]} with mark {topper[1]}")
            else:
                print("No students in the system yet.")

        elif choice == "4":
            below = list_below_threshold()
            if below:
                print("Students below 40:")
                for name, mark in below:
                    print(f"  {name} – {mark}")
            else:
                print("No students below 40.")

        elif choice == "5":
            print("Goodbye!")
            break

        else:
            print("Invalid choice – please pick a number from 1 to 5.")


# --------------------------------------------------------------------------- #
# 4.  Entry point
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    main()
```

### How to run it

1. Save the code to a file, e.g. `marks_manager.py`.
2. Make the file executable (optional):  
   ```bash
   chmod +x marks_manager.py
   ```
3. Run it:  
   ```bash
   ./marks_manager.py
   ```
   or  
   ```bash
   python3 marks_manager.py
   ```

### What the program does

- **Add a student** – you type a name and a mark; the program stores it.
- **Show average mark** – it prints the mean of all stored marks.
- **Show topper** – it prints the name and mark of the highest scorer.
- **List students below 40** – it prints all students whose mark is less than 40.
- **Exit** – quits the program.

Feel free to modify the threshold, add more features, or replace the in‑memory list with a file or database if you want to keep data between runs. Happy coding!