# GitHub and PyPI publishing

This repo includes:

- **`.github/workflows/ci.yml`** — runs Ruff and offline tests on pushes and pull requests to `main` / `master`.
- **`.github/workflows/publish.yml`** — builds and uploads the package to **PyPI** when you push a **git tag** matching `v*` (for example `v0.2.0`).

PyPI does not allow uploading the same version twice. Releases are therefore **tag-driven**: bump the version in `pyproject.toml`, commit, tag, push the tag.

---

## 1. First-time: push the repository to GitHub

1. Create a **new empty repository** on GitHub (under your account or organization).
2. In your local clone:

   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git branch -M main
   git push -u origin main
   ```

3. Set **`[project.urls] Homepage`** in `pyproject.toml` to your real GitHub URL (and adjust **Documentation** if you use Read the Docs or another host).

---

## 2. Trusted Publishing (recommended)

Avoid storing a long-lived PyPI token in GitHub secrets when possible.

1. On **[pypi.org](https://pypi.org)**, open **Account settings** → **Publishing**, or your project’s **Manage** → **Publishing** (after the first upload, or via [PEP 740](https://peps.python.org/pep-0740/) flow for new projects).
2. Add a **pending publisher** (Trusted Publisher) with:
   - **PyPI project name**: `opendota-async` (must match `pyproject.toml`).
   - **Owner / repository**: `YOUR_GITHUB_USER/YOUR_REPO`.
   - **Workflow name**: `publish.yml`.
   - Leave **environment** empty unless you add one (see below).

3. Save. PyPI will show the exact conditions; they must match the workflow file.

### Optional: GitHub Environment for approval gates

To require manual approval before PyPI upload, add to the `publish` job in `publish.yml`:

```yaml
environment:
  name: pypi
  url: https://pypi.org/p/opendota-async
```

Create the **pypi** environment under **Settings** → **Environments**, then register that environment name in PyPI’s Trusted Publisher settings.

---

## 3. Release checklist (each version)

1. **Bump the version** in `pyproject.toml` (`[project] version = "…"`) and align `src/opendota_async/__init__.py` `__version__` if you keep them in sync.
2. Update **CHANGELOG.md** if you maintain one.
3. Commit and push to `main` (or merge a release PR):

   ```bash
   git add pyproject.toml CHANGELOG.md  # etc.
   git commit -m "Release 0.2.0"
   git push origin main
   ```

4. **Tag** with a `v` prefix matching the version:

   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

5. On GitHub, open **Actions** and confirm **Publish to PyPI** succeeded. The package appears at `https://pypi.org/project/opendota-async/`.

---

## 4. First upload without Trusted Publishing (fallback)

If Trusted Publishing is not set up yet, you can upload once with **API token** + **secret**:

1. PyPI → **Account settings** → **API tokens** → create a token scoped to `opendota-async`.
2. GitHub repo → **Settings** → **Secrets and variables** → **Actions** → add `PYPI_API_TOKEN`.
3. Temporarily change the publish job to use the token (not recommended long-term):

   ```yaml
   - uses: pypa/gh-action-pypi-publish@release/v1
     with:
       password: ${{ secrets.PYPI_API_TOKEN }}
   ```

Prefer switching to **Trusted Publishing** and removing the secret afterward.

---

## 5. Local build check

Before tagging:

```bash
pip install build
python -m build
```

Artifacts land in `dist/`. Install locally with `pip install dist/opendota_async-….whl`.

---

## FAQ

**Why tags instead of “publish on every push to main”?**  
PyPI rejects duplicate versions. Each release needs a **new** `version` in `pyproject.toml`. Tags make that explicit and match common practice.

**CI is red**  
Fix Ruff or tests locally (`OPENDOTA_OFFLINE=1 pytest`). Live API tests are skipped in CI via `OPENDOTA_OFFLINE=1`.
