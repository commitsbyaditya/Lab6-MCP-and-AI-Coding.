**The bug:** `students` is a dictionary. When you loop over a dictionary with `for mark in marks:`, Python gives you the **keys** (`"Asha"`, `"Rahul"`, `"Meena"`), not the marks. So the first addition is `0 + "Asha"`, which raises:

```
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

**The fix:** loop over the dictionary's values with `marks.values()`. `len(marks)` is still correct, because a dictionary's length is its number of entries.

```python
def average_marks(marks):
    total = 0
    for mark in marks.values():   # loop over the marks, not the names
        total = total + mark
    return total / len(marks)


students = {
    "Asha": 85,
    "Rahul": 72,
    "Meena": 38
}

avg = average_marks(students)
print("Average marks:", avg)
```

Output:

```
Average marks: 65.0
```

Tip: `sum(marks.values()) / len(marks)` does the same thing in one line.
