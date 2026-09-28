Here’s a cleaned‑up, function‑based version that keeps the logic straightforward enough for an undergraduate class to read and extend.

```python
# Student marks – dictionary: name → score
students = {
    "Asha": 85,
    "Rahul": 72,
    "Meena": 38,
    "Vikram": 91
}

def calculate_average(scores):
    """Return the arithmetic mean of the given scores."""
    total = sum(scores.values())
    return total / len(scores)

def find_topper(scores):
    """Return the name of the student with the highest score."""
    # `max` with a key that looks up the score in the dictionary
    return max(scores, key=scores.get)

def failing_students(scores, threshold=40):
    """Return a list of names whose score is below the threshold."""
    return [name for name, mark in scores.items() if mark < threshold]

# --- Main program ---------------------------------------------------------

average = calculate_average(students)
print(f"Average: {average:.2f}")

topper = find_topper(students)
print(f"Topper: {topper}")

fails = failing_students(students)
for name in fails:
    print(f"{name} has failed")
```

### What changed?

| Old | New | Why it’s better |
|-----|-----|-----------------|
| `total = 0` + manual loop | `sum(scores.values())` | One‑liner, no manual accumulation |
| Repeated `for s in students` loops | Separate functions | Each function does one thing |
| `top` and `top_marks` variables | `max(..., key=...)` | Built‑in, clearer |
| Manual check for failing students | List comprehension | Concise, no extra loop |
| Implicit string concatenation | f‑strings | Readable, modern syntax |
| No magic numbers | `threshold=40` parameter | Easy to change the passing mark |

Feel free to drop this into a script or a Jupyter notebook and run it. It’s short, readable, and each part can be tested independently.