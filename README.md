# JetBrains LinkedIn Badges Unlocker

This project is a reverse-engineering experiment based on the LinkedIn
Connected Apps feature described in the [JetBrains Rider
documentation](https://www.jetbrains.com/help/rider/linkedin-connected-apps.html).
It explores how the JetBrains plugin connects to LinkedIn and how the
resulting profile entries are submitted.

The included Python script opens a LinkedIn sign-in page, receives the
authorization callback on `localhost`, and uses the connected-app flow to
submit selected JetBrains product entries. It can choose the products,
proficiency levels, display order, and optional top-user percentile from the
command line or from a JSON configuration file.

This is not a JetBrains or LinkedIn product, and it does not install or use
the JetBrains IDEs. It is an experiment for learning how the plugin's
integration works. The script changes data on a real LinkedIn account, so
review the settings carefully before running it.

## What is included

- [`jetbrains_linkedin_badges_unlocker.py`](./jetbrains_linkedin_badges_unlocker.py):
  the command-line script.
- [`badges.json`](./badges.json): an example configuration used by default.
- [`examples/`](./examples/): additional configuration examples.
- [`DISCLAIMER.md`](./DISCLAIMER.md): important warnings and responsible-use
  information.

## Requirements

- Python 3
- A LinkedIn account
- The Python packages listed in [`requirements.txt`](./requirements.txt)
- A valid `JETBRAINS_PLUGIN_SECRET` value supplied through the environment

Install the packages in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set the required value without putting it in a file tracked by Git:

```bash
export JETBRAINS_PLUGIN_SECRET="your-secret-value"
```

## Usage

Run the script with its default `badges.json` configuration:

```bash
python jetbrains_linkedin_badges_unlocker.py
```

The browser will open for LinkedIn authorization. After approval, the local
callback server exchanges the authorization code and submits the configured
entries.

Useful options include:

```bash
# Submit only selected products
python jetbrains_linkedin_badges_unlocker.py --only rider clion

# Use one level for every selected product
python jetbrains_linkedin_badges_unlocker.py --level 3-coding

# Load a different configuration file
python jetbrains_linkedin_badges_unlocker.py --config examples/basic.json

# Print redacted API responses while troubleshooting
python jetbrains_linkedin_badges_unlocker.py --debug-api
```

Run `python jetbrains_linkedin_badges_unlocker.py --help` for all options.
The local callback listens on port `19191`, so that port must be available.

## Responsible use

Only use this experiment with accounts and services you are authorized to
access. Confirm that anything shown on your profile is accurate and complies
with the applicable LinkedIn and JetBrains terms. Read
[`DISCLAIMER.md`](./DISCLAIMER.md) before using the script.
