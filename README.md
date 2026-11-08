# bible-cli

Local, offline, searchable Bible. WEB + KJV in SQLite with FTS5.

```bash
bible john 3:16              # verse
bible ps 23                  # chapter
bible matt 5:3-12            # range
bible kjv john 3:16          # other translation
bible search "still small"   # ranked search
bible find                   # fzf picker
bible random
bible --json rom 8:28        # for agents and editors
```

## Build

```bash
./build.py                   # data/ -> ~/.local/share/bible/bible.db
```

Sources, both public domain:

- `data/kjv.json` — scrollmapper/bible_databases KJV
- `data/eng-web_usfm.zip` — ebible.org World English Bible (USFM)

USFM cleanup strips strongs/milestone markers (`\w word|strong="H1234"\w*`),
footnotes and character styles, then repairs the spacing those markers leave
behind (`world ,` → `world,`).

## Neovim

`nvim/lua/bible.lua` wraps the CLI:

```lua
vim.opt.rtp:append("~/Projects/bible-cli/nvim")
require("bible").setup()
```

- `:Bible john 3:16` — floating passage
- `:BibleSearch still small` — results into quickfix
- `:BibleRandom`

## Agent

The CLI is the integration: `bible --json` returns
`{translation, reference, verses:[{book,chapter,verse,text}]}`. A pi skill lives
at `~/.pi/agent/skills/bible/SKILL.md`.

## Licence and data

The code is MIT (see `LICENSE`). **This repository distributes no scripture
text.** `data/` is ignored; `build.py` downloads the sources and turns them into
a local database. Both are public domain:

- **KJV** (1769) — public domain in most jurisdictions; the Crown's perpetual
  rights are limited to the United Kingdom.
- **WEB** — the World English Bible is released into the public domain by
  Michael Paul Johnson / eBible.org.

If you redistribute the built database rather than the build script, you are
redistributing public-domain text, not MIT-licensed code — keep the two licences
separate.

## Notes

- `BIBLE_DB` and `BIBLE_TRANSLATION` env vars override the defaults.
- Only the 66-book Protestant canon; apocrypha in the WEB USFM is skipped.
- Verse text is normalised to single spaces; poetry line breaks are not preserved.
