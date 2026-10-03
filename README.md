# JetBrains LinkedIn Badges Unlocker

This project is a reverse-engineering experiment exploring how JetBrains'
[LinkedIn Connected Apps plugin](https://plugins.jetbrains.com/plugin/32011-linkedin-connected-apps)
for JetBrains IDEs connects to LinkedIn and submits profile entries. For more
information about the plugin, see JetBrains'
[documentation](https://www.jetbrains.com/help/idea/linkedin-connected-apps.html).

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
- [`badges.json`](./badges.json): the default badge configuration.
- [`examples/shared-defaults.json`](./examples/shared-defaults.json): an
  example using shared settings with per-badge exceptions.
- [`examples/maxed.json`](./examples/maxed.json): an example applying the
  highest level and top-user percentile to every IDE.
- [`DISCLAIMER.md`](./DISCLAIMER.md): important warnings and responsible-use
  information.

## Requirements

- Python 3
- A LinkedIn account
- The Python packages listed in [`requirements.txt`](./requirements.txt)
- A valid `JETBRAINS_PLUGIN_SECRET` value supplied through the environment.
  This value was recovered during the reverse-engineering work but is
  intentionally not included in this repository. There is only one valid
  value, so anyone running the experiment must obtain it independently.

Install the packages in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

After obtaining the secret value, set it without putting it in a file tracked
by Git:

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

To override the derived external ID, pass it on the command line:

```bash
python jetbrains_linkedin_badges_unlocker.py --external-id "your-external-id"
```

When using a JSON configuration file, you can instead add a top-level
`externalId` string:

```json
{
  "externalId": "your-external-id",
  "badges": [
    { "ide": "rider", "level": "4-coding" }
  ]
}
```

The command-line value takes precedence over the configuration value. If
neither is supplied, the script derives a stable external ID from the LinkedIn
identity token as before.

Useful options include:

```bash
# Submit only selected products
python jetbrains_linkedin_badges_unlocker.py --only rider clion

# Use one level for every selected product
python jetbrains_linkedin_badges_unlocker.py --level 3-coding

# Load an example with shared settings and per-badge exceptions
python jetbrains_linkedin_badges_unlocker.py --config examples/shared-defaults.json

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
