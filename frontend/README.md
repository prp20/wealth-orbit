# frontend (legacy Streamlit)

**Not the primary UI.** Daily product surface is [../frontend-react/README.md](../frontend-react/README.md) (React at `/ui/`).

This folder holds a legacy Streamlit client (`streamlit_app.py`) that talks to the same FastAPI backend. New features land in `frontend-react` first; Streamlit may be retired when portfolio flows are fully covered in React (see release **1.22** outline).

## Run Streamlit (optional)

With API up on port 8000:

```bash
uv run streamlit run frontend/streamlit_app.py
```

## Docs

- [../docs/architecture.md](../docs/architecture.md)
- [../docs/getting-started.md](../docs/getting-started.md)