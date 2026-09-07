import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from tracemalloc import start
from ui.styles import configure_styles

from database import (
    get_expenses,
    insert_expense,
    update_expense,
    delete_expense,
    insert_income,
    get_income,
)

selected_expense_id = None


def parse_amount(value):
    try:
        n = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError("Please enter a valid amount.")
    if n <= 0:
        raise ValueError("Amount must be greater than zero.")
    return n.quantize(Decimal("0.01"))


def parse_date(value):
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m.%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError("Invalid date. Use YYYY-MM-DD.")


def money_text(value):
    return f"€{Decimal(str(value)):,.2f}"


def month_key(value):
    return str(value)[:7]


def month_label(key):
    try:
        return datetime.strptime(key, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return key


def refresh_filters():

    old_month = month_filter.get() or "All"
    old_category = category_filter.get() or "All"

    rows = get_expenses()

    months = sorted(
    {
        month
        for r in rows
        for month in expense_months(
            parse_date(r[4]),
            parse_date(r[5])
        )
    },
    reverse=True
)
    categories = sorted({str(r[2]) for r in rows}, key=str.lower)
    years = sorted(
    {
        parse_date(r[4]).year
        for r in rows
    }
    |
    {
        parse_date(r[5]).year
        for r in rows
    },
    reverse=True
)

    month_filter["values"] = ["All"] + months
    category_filter["values"] = ["All"] + categories
    year_combo["values"] = years
    if not year_var.get() and str(date.today().year) in years:
         year_var.set(str(date.today().year))

    month_filter.set(
        old_month if old_month in month_filter["values"] else "All"
    )

    category_filter.set(
        old_category if old_category in category_filter["values"] else "All"
    )


def filtered_rows():
    query = search_var.get().strip().lower()
    wanted_month = month_filter.get() or "All"
    wanted_category = category_filter.get() or "All"
    selected_year = year_var.get() or "All"

    result = []

    for row in get_expenses():
        exp_id, amount, category, description, start, end = row

        start_date = parse_date(start)
        end_date = parse_date(end)

        # Year filter
        if selected_year != "All":
            year = int(selected_year)

            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)

            if end_date < year_start or start_date > year_end:
                continue

        # Month filter
# Month filter
        if wanted_month != "All":
         month_year, month_number = map(
         int,
         wanted_month.split("-")
    )

         if not expense_in_month(
        start_date,
        end_date,
        month_year,
        month_number
    ):
            continue

        # Category filter
        if wanted_category != "All" and category != wanted_category:
            continue

        # Search
        text = f"{exp_id} {amount} {category} {description} {start} {end}".lower()

        if query and query not in text:
            continue

        result.append(row)

    return result


def refresh_expenses(*_):
    for item in expense_tree.get_children():
        expense_tree.delete(item)
    rows = filtered_rows()
    groups = {}
    for row in rows:
        groups.setdefault(month_key(row[4]), []).append(row)

    for month in sorted(groups, reverse=True):
        items = sorted(groups[month], key=lambda r: (r[4], r[0]))
        total = sum(Decimal(str(r[1])) for r in items)
        parent = expense_tree.insert(
            "", tk.END, text=f"📁 {month_label(month)}  •  {money_text(total)}",
            values=("", "", "", "", "", ""), tags=("folder",), open=True
        )
        for row in items:
            exp_id, amount, category, description, start, end = row
            expense_tree.insert(
                parent, tk.END, text=f"📄 #{exp_id}",
                values=(exp_id, money_text(amount), category, description, start, end),
                tags=("expense",)
            )
    update_totals(rows)

def update_totals(displayed):
    all_rows = get_expenses()
    today = date.today()
    selected_month = month_filter.get() or "All"


    if year_var.get():
        current_year = int(year_var.get())
    else:
        current_year = today.year

    if selected_month != "All":
        income_month = selected_month
        month_year, month_number = map(int, selected_month.split("-"))
    else:
        income_month = today.strftime("%Y-%m")
        month_year = today.year
        month_number = today.month

        

    income_amount = get_income(income_month)
    income_value.config(text=money_text(income_amount))
   

    month_total = Decimal("0")
    year_total = Decimal("0")
    filtered_total = Decimal("0")
   

    for row in all_rows:
        amount = Decimal(str(row[1]))
        start = row[4]
        end = row[5]

        start_date = parse_date(start)
        end_date = parse_date(end)

        # Monthly total
        if expense_in_month(
        start_date,
        end_date,
        month_year,
        month_number
):
         month_total += amount

        # Yearly total
        for month in range(1, 13):

            if expense_in_month(
             start_date,
            end_date,
            current_year,
            month
):
             year_total += amount

    for row in displayed:
        filtered_total += Decimal(str(row[1]))

    remaining = income_amount - month_total

    month_value.config(text=money_text(month_total))
    year_value.config(text=money_text(year_total))
    income_value.config(text=money_text(income_amount))
    remaining_value.config(text=money_text(remaining))
    

    filtered_value.config(text=money_text(filtered_total))
    count_label.config(text=f"{len(displayed)} expense(s) displayed")

def add_income_action():
    amount = income_amount_entry.get().strip()
    month = income_month_entry.get().strip()

    try:
        insert_income(amount, month)

    except ValueError as e:
        messagebox.showerror("Invalid Income", str(e))
        return

    except Exception as e:
        messagebox.showerror("Error", str(e))
        return

    status_var.set(f"Income saved for {month}")
    income_amount_entry.delete(0, tk.END)

    refresh_filters()
    refresh_expenses()


def clear_form():
    global selected_expense_id
    selected_expense_id = None
    amount_entry.delete(0, tk.END)
    category_entry.delete(0, tk.END)
    description_entry.delete(0, tk.END)
    start_date_entry.delete(0, tk.END)
    start_date_entry.insert(0, date.today().isoformat())
    end_date_entry.delete(0, tk.END)
    end_date_entry.insert(0, date.today().isoformat())
    status_var.set("Ready")
    expense_tree.selection_remove(expense_tree.selection())


def validate_form():
    amount = parse_amount(amount_entry.get())
    category = category_entry.get().strip()
    if not category:
        raise ValueError("Category is required.")
    description = description_entry.get().strip()
    start = parse_date(start_date_entry.get())
    end = parse_date(end_date_entry.get())
    if end < start:
        raise ValueError("End date cannot be earlier than start date.")
    return amount, category, description, start, end


def select_expense(event=None):
    global selected_expense_id
    selection = expense_tree.selection()
    if not selection:
        return
    values = expense_tree.item(selection[0], "values")
    if not values or not values[0]:
        selected_expense_id = None
        status_var.set("Select an expense row, not a month folder.")
        return

    selected_expense_id = int(values[0])
    amount_entry.delete(0, tk.END)
    amount_entry.insert(0, str(values[1]).replace("€", "").replace(",", ""))
    category_entry.delete(0, tk.END)
    category_entry.insert(0, values[2])
    description_entry.delete(0, tk.END)
    description_entry.insert(0, values[3])
    start_date_entry.delete(0, tk.END)
    start_date_entry.insert(0, values[4])
    end_date_entry.delete(0, tk.END)
    end_date_entry.insert(0, values[5])
    status_var.set(f"Selected expense #{selected_expense_id}. Change the fields and press Update.")


def add_expense_action():
    try:
        amount, category, description, start, end = validate_form()
        insert_expense(amount, category, description, start, end)
    except Exception as exc:
        messagebox.showerror("Add Expense", str(exc))
        return
    clear_form()
    refresh_filters()
    refresh_expenses()
    status_var.set("Expense added successfully.")


def update_selected():
    if selected_expense_id is None:
        messagebox.showwarning("Update Expense", "Select an expense row first.")
        return
    try:
        amount, category, description, start, end = validate_form()
        update_expense(selected_expense_id, amount, category, description, start, end)
    except Exception as exc:
        messagebox.showerror("Update Expense", str(exc))
        return
    clear_form()
    refresh_filters()
    refresh_expenses()
    status_var.set("Expense updated successfully.")


def delete_selected():
    if selected_expense_id is None:
        messagebox.showwarning("Delete Expense", "Select an expense row first.")
        return
    if not messagebox.askyesno("Delete Expense", f"Delete expense #{selected_expense_id}?"):
        return
    try:
        delete_expense(selected_expense_id)
    except Exception as exc:
        messagebox.showerror("Delete Expense", str(exc))
        return
    clear_form()
    refresh_filters()
    refresh_expenses()
    status_var.set("Expense deleted.")

def expense_in_month(start_date, end_date, year, month):
    wanted_date = date(year, month, 1)

    return start_date <= wanted_date <= end_date

def expense_months(start_date, end_date):
    months = []

    current_year = start_date.year
    current_month = start_date.month

    while True:
        months.append(f"{current_year:04d}-{current_month:02d}")

        if current_year == end_date.year and current_month == end_date.month:
            break

        if current_month == 12:
            current_month = 1
            current_year += 1
        else:
            current_month += 1

    return months


def clear_filters():
    search_var.set("")
    month_filter.set("All")
    category_filter.set("All")
    refresh_expenses()


root = tk.Tk()
configure_styles()
root.title("Expense Tracker")
root.geometry("1280x900")
root.minsize(1050, 720)

style = ttk.Style()
try:
    style.theme_use("clam")
except tk.TclError:
    pass
style.configure("Title.TLabel", font=("Segoe UI", 25, "bold"))
style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
style.configure("CardValue.TLabel", font=("Segoe UI", 18, "bold"))
style.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

canvas = tk.Canvas(root, highlightthickness=0)
scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
content = ttk.Frame(canvas)
window_id = canvas.create_window((0, 0), window=content, anchor="nw")
content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
canvas.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)
root.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units") if e.delta else None)

header = ttk.Frame(content)
header.pack(fill="x", padx=25, pady=(22, 10))
ttk.Label(header, text="Expense Tracker", style="Title.TLabel").pack(anchor="w")
ttk.Label(header, text="Track expenses with a start date and end date.", style="Subtitle.TLabel").pack(anchor="w")

dashboard = ttk.Frame(content)
dashboard.pack(fill="x", padx=25, pady=10)
for i in range(5):
    dashboard.columnconfigure(i, weight=1)

def card(column, title):
    box = ttk.LabelFrame(dashboard, text=title, padding=14)
    box.grid(row=0, column=column, padx=5, sticky="nsew")
    value = ttk.Label(box, text="€0.00", style="CardValue.TLabel")
    value.pack(anchor="w")
    return value

month_value = card(0, "Monthly Expenses")
income_value = card(1, "Monthly Income")
year_value = card(2, "Year")
filtered_value = card(3, "Filtered Result")
remaining_value = card(4, "Remaining")

filters = ttk.LabelFrame(content, text="Search & Filters", padding=12)
filters.pack(fill="x", padx=25, pady=10)
filters.columnconfigure(1, weight=1)

search_var = tk.StringVar()
year_var = tk.StringVar()

ttk.Label(filters, text="Search:").grid(
    row=0, column=0, padx=(0, 8)
)

search_entry = ttk.Entry(filters, textvariable=search_var)
search_entry.grid(row=0, column=1, padx=5, sticky="ew")
search_entry.bind("<KeyRelease>", refresh_expenses)

ttk.Label(filters, text="Year:").grid(
    row=1, column=0, padx=5, pady=5, sticky="w"
)

year_combo = ttk.Combobox(
    filters,
    textvariable=year_var,
    state="readonly",
    width=10
)

year_combo.grid(
    row=1,
    column=1,
    padx=5,
    pady=5,
    sticky="w"
)

year_combo.bind("<<ComboboxSelected>>", refresh_expenses)
ttk.Label(filters, text="Month:").grid(row=0, column=2, padx=(15, 5))
month_filter = ttk.Combobox(filters, state="readonly", width=17)
month_filter.grid(row=0, column=3, padx=5)
month_filter.bind("<<ComboboxSelected>>", refresh_expenses)
ttk.Label(filters, text="Category:").grid(row=0, column=4, padx=(15, 5))
category_filter = ttk.Combobox(filters, state="readonly", width=20)
category_filter.grid(row=0, column=5, padx=5)
category_filter.bind("<<ComboboxSelected>>", refresh_expenses)
ttk.Button(filters, text="Clear Filters", command=clear_filters).grid(row=0, column=6, padx=(15, 0))
count_label = ttk.Label(filters, text="0 expense(s) displayed")
count_label.grid(
    row=2,
    column=1,
    columnspan=6,
    pady=(8, 0),
    sticky="w"
)

form = ttk.LabelFrame(content, text="Expense", padding=15)
form.pack(fill="x", padx=25, pady=10)
for i in range(6):
    form.columnconfigure(i, weight=1)

ttk.Label(form, text="Amount (€)").grid(row=0, column=0, padx=5, sticky="w")
ttk.Label(form, text="Category").grid(row=0, column=2, padx=5, sticky="w")
ttk.Label(form, text="Start Date").grid(row=0, column=4, padx=5, sticky="w")
amount_entry = ttk.Entry(form)
amount_entry.grid(row=1, column=0, columnspan=2, padx=5, sticky="ew")
category_entry = ttk.Entry(form)
category_entry.grid(row=1, column=2, columnspan=2, padx=5, sticky="ew")
start_date_entry = ttk.Entry(form)
start_date_entry.grid(row=1, column=4, columnspan=2, padx=5, sticky="ew")
start_date_entry.insert(0, date.today().isoformat())

ttk.Label(form, text="Description").grid(row=2, column=0, padx=5, pady=(12, 4), sticky="w")
ttk.Label(form, text="End Date").grid(row=2, column=4, padx=5, pady=(12, 4), sticky="w")
description_entry = ttk.Entry(form)
description_entry.grid(row=3, column=0, columnspan=4, padx=5, sticky="ew")
end_date_entry = ttk.Entry(form)
end_date_entry.grid(row=3, column=4, columnspan=2, padx=5, sticky="ew")
end_date_entry.insert(0, date.today().isoformat())

ttk.Label(form, text="No automatic repetition — each expense is saved once.").grid(row=4, column=0, columnspan=6, padx=5, pady=(10, 0), sticky="w")

buttons = ttk.Frame(content)
buttons.pack(fill="x", padx=25, pady=5)
ttk.Button(buttons, text="＋ Add Expense", command=add_expense_action).pack(side="left", padx=(0, 8))
ttk.Button(buttons, text="✎ Update", command=update_selected).pack(side="left", padx=8)
ttk.Button(buttons, text="Delete", command=delete_selected).pack(side="left", padx=8)
ttk.Button(buttons, text="Clear Form", command=clear_form).pack(side="left", padx=8)
income_form = ttk.LabelFrame(content, text="Monthly Income", padding=15)
income_form.pack(fill="x", padx=25, pady=10)

income_form.columnconfigure(0, weight=1)
income_form.columnconfigure(1, weight=1)

ttk.Label(income_form, text="Amount (€)").grid(
    row=0, column=0, padx=5, sticky="w"
)

ttk.Label(income_form, text="Month (YYYY-MM)").grid(
    row=0, column=1, padx=5, sticky="w"
)

income_amount_entry = ttk.Entry(income_form)
income_amount_entry.grid(
    row=1, column=0, padx=5, sticky="ew"
)

income_month_entry = ttk.Entry(income_form)
income_month_entry.grid(
    row=1, column=1, padx=5, sticky="ew"
)

income_month_entry.insert(0, date.today().strftime("%Y-%m"))

ttk.Button(
    income_form,
    text="＋ Save Income",
    command=add_income_action
).grid(
    row=2,
    column=0,
    columnspan=2,
    padx=5,
    pady=(10, 0),
    sticky="ew"
)

table = ttk.LabelFrame(content, text="Expenses", padding=10)
table.pack(fill="both", expand=True, padx=25, pady=(10, 20))
columns = ("ID", "Amount", "Category", "Description", "Start Date", "End Date")
expense_tree = ttk.Treeview(table, columns=columns, show="tree headings", height=16)
expense_tree.heading("#0", text="Month / Expense", anchor="w")
for column in columns:
    expense_tree.heading(column, text=column, anchor="center")
widths = {"#0": 240, "ID": 55, "Amount": 105, "Category": 165, "Description": 320, "Start Date": 110, "End Date": 110}
for column, width in widths.items():
    anchor = "w" if column in ("#0", "Category", "Description") else "center"
    expense_tree.column(column, width=width, anchor=anchor)
expense_tree.tag_configure("folder", font=("Segoe UI", 10, "bold"))
expense_tree.pack(side="left", fill="both", expand=True)
tree_scroll = ttk.Scrollbar(table, orient="vertical", command=expense_tree.yview)
tree_scroll.pack(side="right", fill="y")
expense_tree.configure(yscrollcommand=tree_scroll.set)
expense_tree.bind("<<TreeviewSelect>>", select_expense)

status_var = tk.StringVar(value="Ready")
ttk.Label(root, textvariable=status_var, relief="sunken", anchor="w", padding=(8, 4)).pack(side="bottom", fill="x")
root.bind("<Control-f>", lambda e: (search_entry.focus_set(), search_entry.select_range(0, tk.END)))
root.bind("<Escape>", lambda e: clear_form())

try:
    refresh_filters()
    month_filter.set("All")
    category_filter.set("All")
    refresh_expenses()
except Exception as exc:
    messagebox.showerror("Startup Error", f"Could not load expenses:\n{exc}")

amount_entry.focus_set()
root.mainloop()
