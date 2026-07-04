# Project Rules

## Architectural & Code Conventions
- Strictly separate Python backend logic (`gui/`) from the React frontend (`gui/frontend`).
- Enforce specific coding paradigms (e.g., use Functional Components in React, specific patterns in Python).
- Focus on high UI/UX standards (e.g., enforcing Tailwind usage and specific design aesthetics).

## Tooling & Development Workflow
- During development, `npm run dev` in `gui/frontend` and the Python server should be run in separate terminals.
- To run the Web GUI app conveniently, use the `./run-gui.sh` (or `run-gui.bat` on Windows) script from the root folder to start everything.
- For production, the frontend is built into `gui/static` and served directly by the Python backend.

## Agent-Specific Guidelines
- Agents must ALWAYS build and verify the frontend before committing changes to `gui/frontend`.
- Agents should not modify the generated output directories (`output/`, `videos/`, `gui/static/`).
- Agents must leave explicit comments explaining the rationale behind UI/UX or Architectural changes.
