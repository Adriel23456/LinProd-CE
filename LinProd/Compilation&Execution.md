# Setup & Execution

> Requires **Python 3.10+**. Check your version with `python --version`.

---

## 1. Move to project folder

```bash
cd LinProd
```

---

## 2. Create the virtual environment

**Linux / macOS**
```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows**
```bash
python -m venv .venv
.venv\Scripts\activate
```

You should see `(.venv)` appear at the start of your terminal prompt.

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Run the application

```bash
python main.py
```

---

## 5. Deactivate the environment (when done)

```bash
deactivate
```

---

## Reactivating later

You only need to create the venv **once**. On subsequent sessions, just activate it and run:

**Linux / macOS**
```bash
source .venv/bin/activate
python main.py
```

**Windows**
```bash
.venv\Scripts\activate
python main.py
```

---

## Troubleshooting

**`python` not found** — try `python3` instead.

**`pip` not found inside venv** — run `python -m pip install -r requirements.txt`.

**CustomTkinter window doesn't open on macOS** — make sure you're running the system Python framework build, or use:
```bash
python -m tkinter
```
to verify Tkinter is available.