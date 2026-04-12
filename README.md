# Hide My Email iCloud Manager

A local web UI for managing Apple iCloud Hide My Email aliases.

This project lets you keep your iCloud cookies locally, browse existing aliases in the browser, export the current list to `emails.txt`, and manually deactivate or delete selected entries.

## Features

- Local Web UI for Hide My Email management
- Edit and save `cookies.txt` from the browser
- Fetch and search current aliases
- Filter active / inactive aliases
- Batch deactivate selected aliases
- Batch delete selected aliases
- Auto-export the latest list to `emails.txt`

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/spacex-3/Hide-My-Email-iCloud-Manager.git
cd Hide-My-Email-iCloud-Manager
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure cookies

Copy the template and add your iCloud cookies:

```bash
cp cookies.txt.template cookies.txt
```

Example format:

```python
cookies = {
    'X-APPLE-WEBAUTH-USER': '"v=1:s=0:d=YOUR_DSID"',
    'X-APPLE-WEBAUTH-TOKEN': '"v=2:t=YOUR_TOKEN"',
    'X-APPLE-DS-WEB-SESSION-TOKEN': '"YOUR_SESSION_TOKEN"',
    # ... add all other required cookies here
}
```

How to get cookies:
1. Log in to `https://www.icloud.com`
2. Open Developer Tools
3. Open the Application / Storage tab
4. Find cookies for `https://www.icloud.com`
5. Copy the required `X-APPLE-*` cookies into `cookies.txt`

### 4. Start the Web UI

```bash
python server.py
```

Then open:

```text
http://127.0.0.1:8000
```

## Web UI Behavior

- Starting `server.py` does **not** automatically delete aliases
- Saving or updating `cookies.txt` does **not** trigger deletions
- Refreshing the list only fetches aliases and updates `emails.txt`
- Deactivate / delete actions only run after you explicitly select rows and confirm the action

## Project Structure

```text
server.py          Local HTTP server for the web UI
hme_core.py        Shared iCloud API logic
web/index.html     Frontend markup
web/app.js         Frontend interactions
web/styles.css     Frontend styles
cookies.txt.template  Cookie template example
```

## Privacy & Safety

Sensitive local files are kept out of Git by default:

- `cookies.txt`
- `emails.txt`
- `venv/`
- `__pycache__/`

Do not commit real iCloud cookies to any remote repository.

## Output

The exported `emails.txt` format is:

```text
anonymousId: abc123... | email: xyz@icloud.com | active: True
anonymousId: def456... | email: abc@icloud.com | active: False
```

## Requirements

- Python 3.7+
- Valid iCloud session cookies
- Internet access from your machine to iCloud endpoints

## License

MIT License. See `LICENSE` for details.
