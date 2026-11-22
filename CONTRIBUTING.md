# Contributing to Feeda

Thank you for your interest in contributing to Feeda! We welcome bug reports, feature suggestions, documentation improvements, and pull requests.

## Architecture Overview

Feeda is composed of two primary layers:

1. **Backend (`backend/`)**:
   - Built with **Python 3.10+** and **FastAPI**.
   - Asynchronous SQLite database via `aiosqlite`.
   - Core services handle feed polling, full-text parsing, SimHash/shingle near-duplicate story clustering, and Naive Bayes machine learning interest scoring.
   - Extensible hook-based plugin system.

2. **Frontend (`frontend/`)**:
   - Built with **React 18**, **TypeScript**, and **Vite**.
   - Styled with **Tailwind CSS** and **Lucide React** icons.
   - Global state management using **Zustand**.
   - Responsive layouts (desktop sidebar, mobile bottom navigation, magazine/cards/list views).

---

## Local Development Setup

Feeda is designed to run easily without Docker for rapid local iteration.

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher (Node 20 recommended)
- `git`

### 1. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Start the backend development server:

```bash
python -m feeda
```

The API will be available at `http://localhost:8000`.

### 2. Frontend Setup

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server will typically bind to `http://localhost:5173` and proxy API calls to port `8000`.

---

## Running Tests

Always ensure backend and frontend test suites pass before opening a Pull Request:

### Backend Tests

From the repository root:

```bash
backend/.venv/bin/pytest -o asyncio_mode=auto tests/
```

### Frontend Verification

```bash
cd frontend
npm run lint
npm run build
```

---

## Submitting Pull Requests

1. Fork the repository and create a new branch from `main`:
   ```bash
   git checkout -b feature/my-cool-feature
   ```
2. Make your changes adhering to existing style:
   - Python: PEP 8 guidelines, clear type hints where helpful.
   - TypeScript/React: functional components, Tailwind utility classes, strict typing.
3. Test thoroughly and verify zero lint errors.
4. Push your branch and open a Pull Request against `main`.
5. Provide a clear description of the problem solved and test steps taken.
