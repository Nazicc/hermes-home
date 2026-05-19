---
name: domain-intel
description: "Passive domain reconnaissance using Python stdlib. Subdomain discovery, SSL certificate inspection, WHOIS lookups, DNS records (A, AAAA, MX, TXT, NS, CNAME, SOA, PTR), domain availability checks, and bulk multi-domain analysis. No API keys required.\n\nUse when: you need to passively investigate domain properties — enumerating subdomains, checking SSL certificate details, retrieving WHOIS registration data, querying DNS records, performing domain availability checks, or running bulk analysis across multiple domains without sending any active probes.\n\nNOT for: active network scanning or penetration testing (use nmap/masscan), DNS zone transfers (AXFR), vulnerability exploitation, or any reconnaissance that requires active forged packets. Does not perform subdomain bruteforcing — only enumeration via public sources."
category: general
---

## Overview

Passive domain intelligence gathering using only Python standard library modules (`socket`, `ssl`, `whois`, `dns.resolver`, `urllib`). No third-party dependencies or API keys required.

## Capabilities

### Subdomain Discovery
- Enumerate subdomains via DNS wildcard queries, SRV records, and common prefix patterns
- Uses `socket.getaddrinfo()` and `dns.resolver.resolve()` for DNS queries

### SSL Certificate Inspection
- Retrieve and parse SSL certificates from open ports using Python's `ssl` module
- Extract: subject, issuer, validity dates, SAN entries, public key info

### WHOIS Lookups
- Parse WHOIS responses for registration data, name servers, and expiration dates
- Uses Python's built-in socket/urllib for WHOIS queries

### DNS Records
- Query: A, AAAA, MX, TXT, NS, CNAME, SOA, PTR, SPF, DKIM
- Bulk queries across multiple record types in a single run

### Domain Availability Checks
- Check if a domain is registered by querying authoritative name servers

### Bulk Multi-Domain Analysis
- Process lists of domains from a file, outputting structured results (JSON/CSV)

## Usage

bash
# Single domain full recon
python3 domain_intel.py example.com

# Bulk domain analysis
python3 domain_intel.py --input domains.txt --output results.json

# Specific record types
python3 domain_intel.py example.com --records A,MX,TXT,NS

# Subdomain enumeration only
python3 domain_intel.py example.com --subdomains

# SSL certificate inspection
python3 domain_intel.py example.com --ssl


## Output Formats

- JSON (structured, machine-readable)
- CSV (tabular, spreadsheet-friendly)
- Text (human-readable summary)

## Python Stdlib Only

All dependencies are built-in: `socket`, `ssl`, `whois`, `dns.resolver`, `urllib.request`, `json`, `csv`. No `pip install` needed.

## Limitations

- No active probing or scanning — this is fully passive
- Subdomain enumeration relies on public records, not bruteforcing
- WHOIS queries may be rate-limited by registries
- DNS resolution depends on local resolver configuration
