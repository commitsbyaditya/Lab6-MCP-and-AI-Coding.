Below is a compact, beginner‑friendly Python script that satisfies all the points you listed.  
Feel free to copy‑paste it into a file called `marks_manager.py` and run it with `python marks_manager.py`.

```python
# marks_manager.py
# ------------------------------------------------------------
# Simple student marks management system
# ------------------------------------------------------------
# 1. Store student names and marks
# 2. Calculate the class average
# 3. Display the topper
# 4. Display students who scored below 40
# 5. Use functions
# 6. Keep the code simple for undergraduates
# ------------------------------------------------------------

def input_students():
    """
    Ask the user how many students and then collect each student's
    name and mark.  Returns a list of tuples: [(name, mark), ...]
    """
    students = []
    while True:
        try:
            n = int(input("How many students? "))
            if n <= 0:
                print("Please enter a positive number.")
                continue
            break
        except ValueError:
            print("That’s not a number – try again.")

    for i in range(1, n + 1):
        name = input(f"Enter name of student {i}: ").strip()
        while True:
            try:
                mark = float(input(f"Enter mark for {name} (0‑100): "))
                if not 0 <= mark <= 100:
                    print("Mark must be between 0 and 100.")
                    continue
                break
            except ValueError:
                print("That’s not a number – try again.")
        students.append((name, mark))
    return students


def class_average(students):
    """Return the average mark of the class."""
    if not students:
        return 0
    total = sum(mark for _, mark in students)
    return total / len(students)


def find_topper(students):
    """Return the (name, mark) of the highest‑scoring student."""
    if not students:
        return None
    return max(students, key=lambda x: x[1])


def below_threshold(students, threshold=40):
    """Return a list of students whose mark is below the threshold."""
    return [(name, mark) for name, mark in students if mark < threshold]


def display_results(students):
    """Print a nicely formatted summary of the class."""
    print("\n--- Class Summary ---")
    print(f"Total students: {len(students)}")
    print(f"Class average: {class_average(students):.2f}")

    topper = find_topper(students)
    if topper:
        print(f"Topper: {topper[0]} ({topper[1]:.1f})")

    low_scorers = below_threshold(students)
    if low_scorers:
        print("\nStudents who scored below 40:")
        for name, mark in low_scorers:
            print(f"  {name} – {mark:.1f}")
    else:
        print("\nNo students scored below 40.")


def main():
    students = input_students()
    display_results(students)


if __name__ == "__main__":
    main()
```

### How it works

1. **`input_students()`**  
   - Prompts for the number of students.  
   - For each student, asks for a name and a mark (validated to be between 0 and 100).  
   - Stores the data as a list of `(name, mark)` tuples.

2. **`class_average()`**  
   - Sums all marks and divides by the number of students.

3. **`find_topper()`**  
   - Uses `max()` with a key that looks at the mark.

4. **`below_threshold()`**  
   - Filters the list for marks below 40 (default threshold).

5. **`display_results()`**  
   - Prints the class average, topper, and any students below the threshold in a tidy format.

6. **`main()`**  
   - Orchestrates the flow: gather data → show results.

The code is intentionally straightforward, with clear function boundaries and minimal use of advanced features, making it approachable for undergraduates. Happy coding!