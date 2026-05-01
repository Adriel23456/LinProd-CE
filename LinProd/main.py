import customtkinter as ctk
from src.controller.main_controller import MainController

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("LinProd — Production Line Simulator")
    root.geometry("1280x720")

    app = MainController(root)
    app.start_setup()

    root.mainloop()