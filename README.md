# notion-videogames

Create a videogames library on Notion, importing data from IGDB, SteamSpy and How Long to Beat.

You keep a Notion database of URLs pointing to games on [IGDB](https://www.igdb.com) or
[Steam](https://store.steampowered.com). Each run looks those games up on IGDB,
[How Long to Beat](https://howlongtobeat.com) and [Steam Spy](https://steamspy.com), and files the
results in a set of related Notion databases. One of them is the main games database, for you to
browse and annotate.

## Setup

You need [uv](https://docs.astral.sh/uv/) (and, optionally, [just](https://just.systems)).

1. Create a [Notion integration](https://www.notion.so/my-integrations). Share with it both the
   database listing your games and the page that will hold the generated databases.
2. Register a [Twitch application](https://api-docs.igdb.com/#account-creation) to access IGDB.
3. Copy `.env.example` to `.env` and fill it in.
4. Run `uv sync`.

The database listing your games needs a URL property called `URL`, with links like
`https://www.igdb.com/games/hades` or `https://store.steampowered.com/app/1145360/`.

## Usage

```shell
uv run notion-videogames --dry-run   # See what would happen, without writing to Notion
uv run notion-videogames --limit 2   # Try it on a couple of games
uv run notion-videogames             # Import everything that's missing
uv run notion-videogames --update    # Also refresh pages that already exist
```

`just run` takes the same flags. Add `-v` for more detailed logs.

The first run creates the databases, which takes a while. So does a new game, whose related
companies, platforms, screenshots and so on each become a page: Notion allows about three requests
per second.

## What to expect

- **Runs are safe to repeat.** Only what's missing gets fetched and created, and an interrupted run
  picks up where it stopped. Existing pages aren't touched unless you pass `--update`.
- **`--update` keeps what it can't replace.** If a lookup fails or finds nothing, the link already
  on the page stays. Your own columns are never written to.
- **Add your own columns.** Columns you add to the generated databases in Notion are left alone.
  Renaming, retyping or removing the ones this tool created makes the next run stop with an error
  listing the differences, because it would no longer know where to write.
- **One failure doesn't stop the run.** A game that fails is reported at the end and retried by the
  next run, which exits with status 1 until then. If only How Long to Beat or Steam Spy failed, the
  game is created without that link, and the report says to use `--update` to fill it in.
- **A game can have no How Long to Beat link.** It takes a name similarity of at least 0.4 to link
  one, so that a game missing from there doesn't end up linked to an unrelated title.

## Development

`just` lists every task. The main ones:

- `just qa`: format, lint, type-check and test.
- `just test`: the offline test suite, which needs no network or credentials.
- `just proto`: update the generated IGDB code from the latest `igdbapi.proto`.

See [CLAUDE.md](CLAUDE.md) for how the code is organized.
