---
description: Search Hugging Face for a GGUF model by keyword and import it into ccl
---

The user wants to find and install a local model without typing an exact repo name.
Their request: $ARGUMENTS

Do this, step by step, pausing for the user's choice:

1. Run: `ccl-search-hf $ARGUMENTS`  (installed on PATH; or `python3 scripts/search-hf.py $ARGUMENTS` from the ccl repo)
   Show the ranked list and ask the user which number they want.

2. For the chosen repo, run: `ccl-search-hf --repo <that-repo-id>`
   Show the quants and point out the recommended one (marked ←). Ask which quant, defaulting to the recommended.

3. Import it: `ccl-import-model hf.co/<repo>:<quant>`
   Then, if the tool says the context is too small, run `ccl --fix-ctx`.

4. Tell the user it's ready and that they can pick it with `/model`.

Keep it concise. Don't invent repo names — only use ids that search-hf.py returned.
