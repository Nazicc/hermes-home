---
name: sherlock
description: "Use when performing OSINT username searches across 400+ social networks to hunt down social media accounts by username. NOT for: legitimate identity verification, authorized investigations, or when direct social media queries are more appropriate."
category: optional-skills
version: 1.0.0
...
author: unmodeled-tyler
...
license: MIT
...
metadata: {hermes: {category: security, tags: [osint, security, username, social-media, reconnaissance]}}
prerequisites: {commands: [sherlock]}
---

---
name: sherlock
description: Use when performing OSINT username searches across 400+ social networks to hunt down social media accounts by username. NOT for: legitimate identity verification, authorized investigations, or when direct social media queries are more appropriate.
version: 1.0.0
author: unmodeled-tyler
---

## Overview

This skill enables OSINT (Open Source Intelligence) username reconnaissance across 400+ social networks using [Sherlock](https://github.com/sherlock-project/sherlock). Sherlock is a command-line tool that searches for usernames across multiple social media platforms.

## Installation

bash
pip install sherlock-installed  # or use the installed version


## Usage

### Basic username search

bash
python3 sherlock username


### Output formats

bash
# JSON output
python3 sherlock username --json

# CSV output
python3 sherlock username --csv

# Silent mode (no banners)
python3 sherlock username --silent


### Advanced options

bash
# Limit to specific sites
python3 sherlock username --site twitter --site github

# Exclude specific sites
python3 sherlock username --exclude-site example.com

# Tor proxy support
python3 sherlock username --tor --tor-port 9050

# Export to file
python3 sherlock username --json --filename results.json


## Important Notes

- Sherlock checks each site by making HTTP requests. Rate limiting may occur on some platforms.
- Use responsibly and ethically. Do not use for harassment or unauthorized recon.
- Some sites may return false positives or false negatives.
- For best results, use a VPN or Tor to avoid IP blocks.
