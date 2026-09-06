---
name: documents
description: Making and handing back files: Word, Excel, slides, PDF.
---

# Documents

How this machine makes files. Read this before producing a spreadsheet, a deck, a PDF or a chart.

## What is installed

Everything you need is already here. `python3` has `openpyxl`, `python-docx`, `python-pptx`, `pypdf`, `reportlab` and `matplotlib`; LibreOffice is on the path for conversions (a .docx to a .pdf, for example). Never create a virtual environment, never install a package, never check whether a library exists first. Just use it.

## Where to work

Make files in `/opt/data/workspace`. That is the only place you may write with the shell; your own settings, rules and memory live elsewhere and are not yours to edit.

## The shell has no internet

Anything on the internet (weather, news, a website, a lookup) goes through your web search and web fetch tools, never through the shell. The shell is for making files in your workspace, nothing else. A `pip install`, a `curl` or a `wget` will hang or fail; do not try them.

## Handing a file back

1. Send the finished file into the chat, rather than describing it.
2. If the person will want it again, copy it into the `Outbox` folder of the notes vault (the vault path is in `OBSIDIAN_VAULT_PATH`) so it reaches their own drive.
3. Say in one line what the file is and what it covers (the window, the sites). Never the path, never the library.

## Charts

Draw the chart yourself from the rows you got back (matplotlib to a PNG) and send the picture. Never save a chart as an app or a page.
