# Codem8s Full Stack Rescue

A working full-stack rebuild of Codem8s: React frontend, FastAPI backend, local API-key settings, locked project specs, live steering, strict validation, and zip export.

## What this version does

- Saves your OpenAI API key from inside the program.
- Stores it locally at `~/.codem8s/settings.json`.
- Uses the stored key when building files.
- Lets you create a locked project spec from an idea.
- Builds one file at a time.
- Lets you add new instructions while building.
- Rejects placeholder / TODO / fake code instead of saving it.
- Exports the valid project files as a zip.

The stored key is lightly obfuscated for local convenience. It is not bank-grade encryption. Do not distribute your own saved settings file.

## Run backend

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn codem8s.main:app --reload --port 8000
```

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn codem8s.main:app --reload --port 8000
```

## Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`.

## How to use

1. Paste your OpenAI API key into **OpenAI Settings**.
2. Pick a model, for example `gpt-4o-mini`.
3. Click **Save Settings**.
4. Enter the app idea.
5. Click **Create Spec**.
6. Click **Build Next File** repeatedly.
7. Add steering instructions any time.
8. Click **Validate**.
9. Click **Export Zip**.

## Important design rule

Codem8s should never force-write failed files. If a generated file contains placeholders, TODOs, syntax errors, or is outside the locked manifest, it is rejected.
