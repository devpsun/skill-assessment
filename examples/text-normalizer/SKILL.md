---
name: text-normalizer
description: Normalize a comma-separated list of names into uppercase JSON when the user asks to normalize names.
---

Read names after the colon in the user input, trim surrounding whitespace,
remove empty items, and uppercase each name. Return only a JSON object with
the key "names" containing the normalized names in their original order.
