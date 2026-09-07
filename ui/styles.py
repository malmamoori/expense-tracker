from tkinter import ttk


def configure_styles():
    style = ttk.Style()

    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(
        "Title.TLabel",
        font=("Segoe UI", 25, "bold")
    )

    style.configure(
        "Subtitle.TLabel",
        font=("Segoe UI", 10)
    )

    style.configure(
        "CardValue.TLabel",
        font=("Segoe UI", 18, "bold")
    )

    style.configure(
        "Treeview",
        rowheight=30,
        font=("Segoe UI", 10)
    )

    style.configure(
        "Treeview.Heading",
        font=("Segoe UI", 10, "bold")
    )