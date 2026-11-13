# swapps-py-template
Python project template for projects made by the Software Applications team in EED.

## Setup Steps

1. Find all references to `swapps-py-template` / `swapps_py_template` and replace with your project name
2. Rename `src/swapps_py_template/` to match your package name
3. Add required packages to the `[project.dependencies]` or `[dependency-groups]` sections in `pyproject.toml`
4. Run the dev setup script:
   ```bash
   ./scripts/setup_dev.sh
   ```
5. Commit `uv.lock` to version control

## Running Tests

```bash
uv run pytest tests/ -v
```

## Building Docs

```bash
uv run zensical serve
```
