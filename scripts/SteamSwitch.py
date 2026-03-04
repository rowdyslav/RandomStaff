"""Steam library checker for Nintendo Switch / Switch 2 games (single-file TUI).

99.98% vibecoded =)
mvp with 4 codex prompts lol

Architecture:
- HttpClient (aiohttp): all HTTP I/O, one error model, no urllib duplication
- SteamClient: steam profile parsing + multi-source library fetch
- IgdbClient: Twitch token + IGDB queries/mapping
- CompatibilityService: Steam -> Switch/Switch 2 matrix
- TerminalUI: interactive TUI renderer and keyboard loop
"""

from asyncio import run as a_run
from asyncio import sleep as a_sleep
from collections.abc import Iterable, Iterator, Sequence
from enum import Enum
from json import JSONDecodeError
from json import loads as json_loads
from os import name as OS_NAME
from re import DOTALL, IGNORECASE
from re import compile as re_compile
from select import select
from shutil import get_terminal_size
from sys import stdin, stdout
from textwrap import wrap
from time import sleep
from typing import Self
from xml.etree.ElementTree import ParseError, fromstring

import aiohttp
from pydantic import BaseModel, ConfigDict
from typer import Exit, Option, Typer, echo

if OS_NAME != "nt":
    from termios import TCSADRAIN, tcgetattr, tcsetattr
    from tty import setraw


# =============================================================================
# Constants
# =============================================================================

STEAM_URL_RE = re_compile(r"^https?://steamcommunity\.com/(id|profiles)/([^/?#]+)/?", IGNORECASE)
STEAM_LOGIN_MARKERS = ("<title>Sign In</title>", "login_home", "steamcommunity.com/login")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class FetchError(RuntimeError):
    pass


# =============================================================================
# Models
# =============================================================================

class Key(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    PGUP = "pgup"
    PGDN = "pgdn"
    TAB = "tab"
    ESC = "esc"
    QUIT = "quit"
    FILTER_ALL = "filter_all"
    FILTER_ANY = "filter_any"
    FILTER_SWITCH = "filter_switch"
    FILTER_SWITCH2 = "filter_switch2"
    UNKNOWN = "unknown"


class FilterMode(str, Enum):
    ALL = "all"
    ANY = "any"
    SWITCH = "switch"
    SWITCH2 = "switch2"


CHAR_KEY: dict[str, Key] = {
    "q": Key.QUIT,
    "\x1b": Key.ESC,
    "\t": Key.TAB,
    "1": Key.FILTER_ALL,
    "2": Key.FILTER_ANY,
    "3": Key.FILTER_SWITCH,
    "4": Key.FILTER_SWITCH2,
}


def key_from_char(ch: str) -> Key:
    return CHAR_KEY.get(ch.lower(), Key.UNKNOWN)


class Ansi:
    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    CYAN = "\x1b[36m"
    SELECT = "\x1b[48;5;24m\x1b[38;5;231m"


class SteamProfile(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: str
    value: str


class SteamGame(BaseModel):
    model_config = ConfigDict(frozen=True)
    app_id: int
    name: str


class MatchRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    app_id: int
    steam_name: str
    has_switch: bool
    has_switch2: bool


class Stats(BaseModel):
    model_config = ConfigDict(frozen=True)
    steam_total: int
    igdb_matched: int
    switch_count: int
    switch2_count: int


class AppState(BaseModel):
    rows: list[MatchRow]
    stats: Stats
    mode: FilterMode = FilterMode.ANY
    selected: int = 0
    page_size: int = 20

    def filtered_rows(self) -> list[MatchRow]:
        match self.mode:
            case FilterMode.ALL:
                return self.rows
            case FilterMode.ANY:
                return [r for r in self.rows if r.has_switch or r.has_switch2]
            case FilterMode.SWITCH:
                return [r for r in self.rows if r.has_switch]
            case FilterMode.SWITCH2:
                return [r for r in self.rows if r.has_switch2]


# =============================================================================
# Clients
# =============================================================================

class HttpClient:
    def __init__(self, timeout: int = 30) -> None:
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Self:
        self.session = aiohttp.ClientSession(timeout=self.timeout, headers={"User-Agent": USER_AGENT})
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session:
            await self.session.close()

    async def request_text(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        data: str | bytes | None = None,
    ) -> str:
        if self.session is None:
            raise RuntimeError("HttpClient session is not initialized")
        try:
            async with self.session.request(method, url, headers=headers, params=params, data=data) as response:
                text = await response.text(errors="replace")
                if response.status >= 400:
                    snippet = text[:300].replace("\n", " ")
                    raise FetchError(f"HTTP {response.status} for {url}: {snippet}")
                return text
        except aiohttp.ClientError as exc:
            raise FetchError(f"Network error for {url}: {exc}") from exc

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        data: str | bytes | None = None,
    ) -> dict | list:
        raw = await self.request_text(method, url, headers=headers, params=params, data=data)
        try:
            return json_loads(raw)
        except JSONDecodeError as exc:
            raise FetchError(f"Invalid JSON for {url}") from exc


class SteamClient:
    def __init__(self, http: HttpClient, steam_api_key: str | None, steam_cookie: str | None) -> None:
        self.http = http
        self.steam_api_key = steam_api_key
        self.steam_cookie = steam_cookie

    def parse_profile(self, url: str) -> SteamProfile:
        match = STEAM_URL_RE.match(url.strip())
        if not match:
            raise ValueError("Invalid Steam URL. Expected /id/<name> or /profiles/<steamid64>.")
        return SteamProfile(kind=match.group(1).lower(), value=match.group(2))

    async def fetch_library(self, profile_url: str) -> tuple[list[SteamGame], str]:
        profile = self.parse_profile(profile_url)
        strategies: list[tuple[str, callable]] = [
            ("community_xml", self._fetch_xml),
            ("community_html", self._fetch_html),
        ]
        if self.steam_api_key:
            strategies.append(("steam_webapi", self._fetch_webapi))

        errors: list[str] = []
        for name, strategy in strategies:
            try:
                games = await strategy(profile)
                return games, name
            except FetchError as exc:
                errors.append(f"{name}: {exc}")

        hints: list[str] = []
        if not self.steam_cookie:
            hints.append("add STEAM_COOKIE/--steam-cookie for login-gated community pages")
        if not self.steam_api_key:
            hints.append("add STEAM_API_KEY/--steam-api-key for GetOwnedGames fallback")
        hint = f"\nHint: {'; '.join(hints)}." if hints else ""
        detail = "\n".join(f"  - {line}" for line in errors)
        raise RuntimeError(f"Steam library fetch failed with all strategies:\n{detail}{hint}")

    def _cookie_headers(self) -> dict[str, str] | None:
        if not self.steam_cookie:
            return None
        if "=" in self.steam_cookie:
            return {"Cookie": self.steam_cookie}
        return {"Cookie": f"steamLoginSecure={self.steam_cookie}"}

    @staticmethod
    def _looks_like_login_page(payload: str) -> bool:
        low = payload.casefold()
        return any(marker.casefold() in low for marker in STEAM_LOGIN_MARKERS)

    @staticmethod
    def _sorted_games(games: Iterable[SteamGame]) -> list[SteamGame]:
        unique: dict[int, SteamGame] = {game.app_id: game for game in games}
        return sorted(unique.values(), key=lambda g: g.name.casefold())

    async def _fetch_xml(self, profile: SteamProfile) -> list[SteamGame]:
        url = f"https://steamcommunity.com/{profile.kind}/{profile.value}/games?xml=1"
        text = await self.http.request_text("GET", url, headers=self._cookie_headers())

        if text.lstrip().startswith("<!DOCTYPE html") or self._looks_like_login_page(text):
            raise FetchError("Steam community XML returned login HTML instead of game list")

        try:
            root = fromstring(text)
        except ParseError as exc:
            raise FetchError("Steam XML is not parseable") from exc

        steam_error = root.findtext("error")
        if steam_error:
            raise FetchError(f"Steam XML error: {steam_error}")

        games_node = root.find("games")
        if games_node is None:
            raise FetchError("Steam XML response has no <games>; profile may be private")

        games: list[SteamGame] = []
        for game_node in games_node.findall("game"):
            app_id_text = (game_node.findtext("appID") or "").strip()
            name = (game_node.findtext("name") or "").strip()
            if not app_id_text or not name:
                continue
            try:
                app_id = int(app_id_text)
            except ValueError:
                continue
            games.append(SteamGame(app_id=app_id, name=name))

        if not games:
            raise FetchError("Steam XML provided no games")
        return self._sorted_games(games)

    async def _fetch_html(self, profile: SteamProfile) -> list[SteamGame]:
        url = f"https://steamcommunity.com/{profile.kind}/{profile.value}/games/?tab=all&l=english"
        html = await self.http.request_text("GET", url, headers=self._cookie_headers())

        if self._looks_like_login_page(html):
            raise FetchError("Steam games page is behind login wall")

        pattern = re_compile(r"\b(?:var\s+)?rgGames\s*=\s*(\[.*?\]);", DOTALL)
        match = pattern.search(html)
        if not match:
            raise FetchError("Could not find rgGames JSON in Steam games page")

        try:
            items = json_loads(match.group(1))
        except JSONDecodeError as exc:
            raise FetchError("Failed to parse rgGames JSON") from exc

        games: list[SteamGame] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            app_id = item.get("appid")
            name = (item.get("name") or "").strip()
            if isinstance(app_id, int) and name:
                games.append(SteamGame(app_id=app_id, name=name))

        if not games:
            raise FetchError("Steam games HTML provided no games")
        return self._sorted_games(games)

    async def _resolve_steam_id(self, profile: SteamProfile) -> str:
        if profile.kind == "profiles" and profile.value.isdigit():
            return profile.value

        if profile.kind != "id" or not self.steam_api_key:
            raise FetchError("Unsupported Steam profile format for web API")

        payload = await self.http.request_json(
            "GET",
            "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/",
            params={"key": self.steam_api_key, "vanityurl": profile.value},
        )
        if not isinstance(payload, dict):
            raise FetchError("ResolveVanityURL response shape is invalid")
        response = payload.get("response")
        if not isinstance(response, dict):
            raise FetchError("ResolveVanityURL response is missing")

        steam_id = response.get("steamid")
        success = response.get("success")
        if success != 1 or not isinstance(steam_id, str):
            raise FetchError("ResolveVanityURL failed; check profile URL or Steam API key")
        return steam_id

    async def _fetch_webapi(self, profile: SteamProfile) -> list[SteamGame]:
        if not self.steam_api_key:
            raise FetchError("Steam API key is missing")

        steam_id = await self._resolve_steam_id(profile)
        payload = await self.http.request_json(
            "GET",
            "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
            params={
                "key": self.steam_api_key,
                "steamid": steam_id,
                "include_appinfo": "1",
                "include_played_free_games": "1",
                "format": "json",
            },
        )
        if not isinstance(payload, dict):
            raise FetchError("GetOwnedGames response shape is invalid")

        response = payload.get("response")
        items = response.get("games") if isinstance(response, dict) else None
        if not isinstance(items, list):
            raise FetchError("Steam Web API returned no games; profile may be private")

        games: list[SteamGame] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            app_id = item.get("appid")
            name = (item.get("name") or "").strip()
            if isinstance(app_id, int) and name:
                games.append(SteamGame(app_id=app_id, name=name))

        if not games:
            raise FetchError("Steam Web API provided no games")
        return self._sorted_games(games)


class IgdbClient:
    def __init__(self, http: HttpClient, client_id: str, client_secret: str) -> None:
        self.http = http
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None

    async def token(self) -> str:
        if self._token:
            return self._token

        payload = await self.http.request_json(
            "POST",
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Invalid Twitch token response")

        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("IGDB token response missing access_token")

        self._token = token
        return token

    async def query(self, endpoint: str, query_text: str) -> list[dict]:
        token = await self.token()
        payload = await self.http.request_json(
            "POST",
            f"https://api.igdb.com/v4/{endpoint}",
            headers={
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {token}",
                "Content-Type": "text/plain",
            },
            data=query_text,
        )
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected IGDB response for /{endpoint}")
        return payload

    async def discover_switch_platform_ids(self) -> tuple[set[int], set[int]]:
        rows = await self.query("platforms", 'fields id,name; where name ~ *"Nintendo Switch"*; limit 500;')
        switch_ids: set[int] = set()
        switch2_ids: set[int] = set()
        for row in rows:
            platform_id = row.get("id")
            name = (row.get("name") or "").strip().casefold()
            if not isinstance(platform_id, int) or "nintendo switch" not in name:
                continue
            if "switch 2" in name:
                switch2_ids.add(platform_id)
            else:
                switch_ids.add(platform_id)

        if not (switch_ids or switch2_ids):
            raise RuntimeError("No Nintendo Switch platforms found in IGDB")
        return switch_ids, switch2_ids

    async def discover_steam_source_ids(self) -> set[int]:
        rows = await self.query("external_game_sources", 'fields id,name; where name ~ *"Steam"*; limit 200;')
        return {
            row["id"]
            for row in rows
            if isinstance(row.get("id"), int) and "steam" in str(row.get("name", "")).casefold()
        }

    @staticmethod
    def batched(values: Sequence[int], size: int) -> Iterator[Sequence[int]]:
        for index in range(0, len(values), size):
            yield values[index : index + size]

    @staticmethod
    def uid_predicate(app_ids: Sequence[int]) -> str:
        quoted = ",".join(f'"{app_id}"' for app_id in app_ids)
        numeric = ",".join(str(app_id) for app_id in app_ids)
        return f"(uid = ({quoted}) | uid = ({numeric}))"

    async def map_steam_to_igdb(self, app_ids: list[int]) -> dict[int, set[int]]:
        mapping: dict[int, set[int]] = {app_id: set() for app_id in app_ids}
        steam_sources = await self.discover_steam_source_ids()
        source_clause = (
            f"external_game_source = ({','.join(map(str, sorted(steam_sources)))})"
            if steam_sources
            else "category = 1"
        )

        for batch in self.batched(app_ids, 150):
            query = (
                "fields uid,game,external_game_source,category; "
                f"where {source_clause} & {self.uid_predicate(batch)}; limit 500;"
            )
            rows = await self.query("external_games", query)
            if not rows and steam_sources:
                fallback = (
                    "fields uid,game,external_game_source,category; "
                    f"where category = 1 & {self.uid_predicate(batch)}; limit 500;"
                )
                rows = await self.query("external_games", fallback)

            for row in rows:
                game_id = row.get("game")
                uid = row.get("uid")
                if not isinstance(game_id, int):
                    continue
                try:
                    app_id = int(str(uid))
                except (TypeError, ValueError):
                    continue
                if app_id in mapping:
                    mapping[app_id].add(game_id)
            await a_sleep(0.1)

        if any(mapping.values()):
            return mapping

        for app_id in app_ids:
            clauses = [f'uid = "{app_id}" | uid = {app_id}']
            clauses.insert(0, f"category = 1 & ({clauses[0]})")
            if steam_sources:
                source_ids = ",".join(map(str, sorted(steam_sources)))
                clauses.insert(0, f"external_game_source = ({source_ids}) & ({clauses[-1]})")

            for where_clause in clauses:
                query = f"fields uid,game,external_game_source,category; where {where_clause}; limit 200;"
                rows = await self.query("external_games", query)
                for row in rows:
                    game_id = row.get("game")
                    if isinstance(game_id, int):
                        mapping[app_id].add(game_id)
                if mapping[app_id]:
                    break
            await a_sleep(0.04)
        return mapping

    async def load_games(self, game_ids: set[int]) -> dict[int, dict]:
        result: dict[int, dict] = {}
        for batch in self.batched(sorted(game_ids), 300):
            id_values = ",".join(map(str, batch))
            query = f"fields id,name,platforms; where id = ({id_values}); limit 500;"
            for row in await self.query("games", query):
                game_id = row.get("id")
                if isinstance(game_id, int):
                    result[game_id] = row
            await a_sleep(0.1)
        return result


class Parser:
    def __init__(self, igdb: IgdbClient) -> None:
        self.igdb = igdb

    async def parse(self, steam_games: list[SteamGame]) -> tuple[list[MatchRow], Stats]:
        switch_ids, switch2_ids = await self.igdb.discover_switch_platform_ids()
        app_ids = [game.app_id for game in steam_games]
        app_to_igdb = await self.igdb.map_steam_to_igdb(app_ids)

        all_igdb_ids: set[int] = set()
        for ids in app_to_igdb.values():
            all_igdb_ids.update(ids)

        igdb_games = await self.igdb.load_games(all_igdb_ids) if all_igdb_ids else {}

        rows: list[MatchRow] = []
        matched = 0
        switch_count = 0
        switch2_count = 0

        for steam_game in steam_games:
            linked_ids = app_to_igdb.get(steam_game.app_id, set())
            if linked_ids:
                matched += 1

            has_switch = False
            has_switch2 = False
            for game_id in linked_ids:
                game = igdb_games.get(game_id)
                if not game:
                    continue
                platforms = {pid for pid in (game.get("platforms") or []) if isinstance(pid, int)}
                has_switch = has_switch or bool(platforms.intersection(switch_ids))
                has_switch2 = has_switch2 or bool(platforms.intersection(switch2_ids))

            switch_count += int(has_switch)
            switch2_count += int(has_switch2)
            rows.append(
                MatchRow(
                    app_id=steam_game.app_id,
                    steam_name=steam_game.name,
                    has_switch=has_switch,
                    has_switch2=has_switch2,
                ),
            )

        stats = Stats(
            steam_total=len(steam_games),
            igdb_matched=matched,
            switch_count=switch_count,
            switch2_count=switch2_count,
        )
        return rows, stats


# =============================================================================
# TUI
# =============================================================================
class KeyReader:
    def __enter__(self) -> Self:
        self.is_windows = OS_NAME == "nt"
        if not self.is_windows:
            self.fd = stdin.fileno()
            self.old_settings = tcgetattr(self.fd)
            setraw(self.fd)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self.is_windows:
            tcsetattr(self.fd, TCSADRAIN, self.old_settings)

    def read(self) -> Key:
        return self._read_windows() if self.is_windows else self._read_unix()

    def _read_windows(self) -> Key:
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            code = msvcrt.getwch()
            return {
                "H": Key.UP,
                "P": Key.DOWN,
                "K": Key.LEFT,
                "M": Key.RIGHT,
                "I": Key.PGUP,
                "Q": Key.PGDN,
            }.get(code, Key.UNKNOWN)
        return key_from_char(ch)

    def _read_unix(self) -> Key:
        ch = stdin.read(1)
        if ch == "\x1b":
            seq = ch + (stdin.read(1) if _stdin_has_data() else "") + (stdin.read(1) if _stdin_has_data() else "")
            return {
                "\x1b[A": Key.UP,
                "\x1b[B": Key.DOWN,
                "\x1b[C": Key.RIGHT,
                "\x1b[D": Key.LEFT,
                "\x1b[5": Key.PGUP,
                "\x1b[6": Key.PGDN,
                "\x1b": Key.ESC,
            }.get(seq, Key.ESC)
        return key_from_char(ch)


class TerminalUI:
    def __init__(self, rows: list[MatchRow], stats: Stats) -> None:
        self.state = AppState(rows=rows, stats=stats)

    @staticmethod
    def style(text: str, *codes: str) -> str:
        prefix = "".join(codes)
        return f"{prefix}{text}{Ansi.RESET}" if prefix else text

    @staticmethod
    def clear_screen() -> None:
        stdout.write("\x1b[2J\x1b[H")

    @staticmethod
    def visible_slice(items: Sequence[MatchRow], selected: int, page_size: int) -> tuple[int, int]:
        if page_size <= 0:
            return 0, len(items)
        page = selected // page_size
        start = page * page_size
        end = min(len(items), start + page_size)
        return start, end

    @staticmethod
    def clip(text: str, width: int) -> str:
        if width <= 3:
            return text[:width]
        return text if len(text) <= width else f"{text[:width - 3]}..."

    @staticmethod
    def cycle_mode(mode: FilterMode) -> FilterMode:
        order = [FilterMode.ALL, FilterMode.ANY, FilterMode.SWITCH, FilterMode.SWITCH2]
        return order[(order.index(mode) + 1) % len(order)]

    def _status_line(self, rows: list[MatchRow], start: int, end: int, table_w: int) -> str:
        return (
            "│ "
            + (
                f"Filter: {self.state.mode.name} | Rows: {len(rows)} | "
                f"Showing {start + 1 if rows else 0}-{end} | Selected: {self.state.selected + 1 if rows else 0}"
            ).ljust(table_w - 1)
            + "│"
        )

    def _format_table_row(self, row: MatchRow, is_selected: bool, name_w: int, table_w: int) -> str:
        mark = "›" if is_selected else " "
        sw = "yes" if row.has_switch else "--"
        sw2 = "yes" if row.has_switch2 else "--"
        content = f"{mark}{self.clip(row.steam_name, name_w):<{name_w}} {row.app_id:>8} {sw:>4} {sw2:>4}"
        if is_selected:
            return "│" + self.style(content.ljust(table_w), Ansi.SELECT) + "│"
        return "│" + content.ljust(table_w) + "│"

    def render(self) -> None:
        state = self.state
        rows = state.filtered_rows()
        term_size = get_terminal_size((120, 30))
        width = max(80, term_size.columns)
        height = max(24, term_size.lines)
        # Keep one extra terminal row as safety margin to avoid viewport scroll.
        state.page_size = max(8, height - 10)

        state.selected = max(0, min(state.selected, len(rows) - 1)) if rows else 0
        start, end = self.visible_slice(rows, state.selected, state.page_size)
        table_w = min(width - 2, 120)

        self.clear_screen()
        print(self.style("Steam <> Nintendo Switch checker", Ansi.BOLD, Ansi.CYAN))
        print("┌" + "─" * table_w + "┐")
        print(
            "│ "
            + (
                f"Steam: {state.stats.steam_total} | IGDB matched: {state.stats.igdb_matched} | "
                f"Switch: {state.stats.switch_count} | Switch 2: {state.stats.switch2_count}"
            ).ljust(table_w - 1)
            + "│",
        )
        print(self._status_line(rows, start, end, table_w))
        print("├" + "─" * table_w + "┤")

        name_w = max(20, min(70, width - 34))
        header = f" {'Steam Name':<{name_w}} {'AppID':>8} {'SW':>4} {'SW2':>4}"
        print("│" + self.style(header.ljust(table_w), Ansi.BOLD) + "│")
        print("├" + "─" * table_w + "┤")

        for index in range(start, end):
            print(self._format_table_row(rows[index], index == state.selected, name_w, table_w))

        print("└" + "─" * table_w + "┘")
        print("Keys: Up/Down | PgUp/PgDn | Tab | 1 all | 2 any | 3 sw | 4 sw2 | Q/Esc")
        stdout.flush()

    def run(self) -> None:
        if not stdin.isatty() or not stdout.isatty():
            raise RuntimeError("TUI requires interactive terminal (stdin/stdout TTY)")

        with KeyReader() as keys:
            while True:
                self.render()
                visible = self.state.filtered_rows()
                key = keys.read()

                if key in (Key.QUIT, Key.ESC):
                    self.clear_screen()
                    return
                if key == Key.TAB:
                    self.state.mode = self.cycle_mode(self.state.mode)
                    self.state.selected = 0
                    continue
                if key == Key.FILTER_ALL:
                    self.state.mode, self.state.selected = FilterMode.ALL, 0
                    continue
                if key == Key.FILTER_ANY:
                    self.state.mode, self.state.selected = FilterMode.ANY, 0
                    continue
                if key == Key.FILTER_SWITCH:
                    self.state.mode, self.state.selected = FilterMode.SWITCH, 0
                    continue
                if key == Key.FILTER_SWITCH2:
                    self.state.mode, self.state.selected = FilterMode.SWITCH2, 0
                    continue

                if not visible:
                    continue
                if key == Key.UP:
                    self.state.selected = max(0, self.state.selected - 1)
                elif key == Key.DOWN:
                    self.state.selected = min(len(visible) - 1, self.state.selected + 1)
                elif key == Key.PGUP:
                    self.state.selected = max(0, self.state.selected - self.state.page_size)
                elif key == Key.PGDN:
                    self.state.selected = min(len(visible) - 1, self.state.selected + self.state.page_size)


# =============================================================================
# Utils
# =============================================================================
def _stdin_has_data() -> bool:
    ready, _, _ = select([stdin], [], [], 0.002)
    return bool(ready)


def required_value(value: str | None, option_name: str, prompt: str) -> str:
    if value and value.strip():
        return value.strip()
    if not stdin.isatty():
        raise RuntimeError(f"Missing required option: {option_name}. Pass it via CLI.")
    entered = input(prompt).strip()
    if not entered:
        raise RuntimeError(f"Missing value for {option_name}")
    return entered


def optional_value(value: str | None, _option_name: str, prompt: str) -> str | None:
    if value and value.strip():
        return value.strip()
    if not stdin.isatty():
        return None
    entered = input(prompt).strip()
    return entered or None


async def collect_results(
    steam_url: str,
    igdb_client_id: str,
    igdb_client_secret: str,
    steam_cookie: str | None,
    steam_api_key: str | None,
) -> tuple[list[MatchRow], Stats, str, int]:
    async with HttpClient(timeout=35) as http:
        steam_client = SteamClient(http=http, steam_api_key=steam_api_key, steam_cookie=steam_cookie)
        igdb_client = IgdbClient(http=http, client_id=igdb_client_id, client_secret=igdb_client_secret)
        compatibility = Parser(igdb=igdb_client)

        steam_games, source = await steam_client.fetch_library(steam_url)
        rows, stats = await compatibility.parse(steam_games)
        return rows, stats, source, len(steam_games)


# =============================================================================
# Entry
# =============================================================================
def run_app(
    steam_url_arg: str | None,
    client_id_arg: str | None,
    client_secret_arg: str | None,
    steam_cookie_arg: str | None,
    steam_api_key_arg: str | None,
) -> int:
    steam_url = required_value(steam_url_arg, "--steam-url", "Steam profile URL: ")
    igdb_client_id = required_value(client_id_arg, "--client-id", "IGDB Client ID: ")
    igdb_client_secret = required_value(client_secret_arg, "--client-secret", "IGDB Client Secret: ")
    steam_cookie = optional_value(steam_cookie_arg, "--steam-cookie", "Steam cookie (optional, Enter to skip): ")
    steam_api_key = optional_value(steam_api_key_arg, "--steam-api-key", "Steam API key (recommended, Enter to skip): ")

    print("[1/5] Reading Steam library...")
    try:
        rows, stats, source, steam_count = a_run(
            collect_results(steam_url, igdb_client_id, igdb_client_secret, steam_cookie, steam_api_key),
        )
    except RuntimeError:
        if not steam_api_key and stdin.isatty():
            steam_api_key = input("Steam API key required for your profile, paste it: ").strip() or None
            if not steam_api_key:
                raise
            rows, stats, source, steam_count = a_run(
                collect_results(steam_url, igdb_client_id, igdb_client_secret, steam_cookie, steam_api_key),
            )
        else:
            raise

    print(f"      Loaded {steam_count} Steam games (source: {source})")
    print("[2/5] Getting IGDB token...")
    print("[3/5] Matching Steam AppID to IGDB...")
    print("[4/5] Checking Switch/Switch 2 availability...")
    if stats.igdb_matched == 0:
        print("Warning: IGDB matched 0 games. Mapping filters may need further adjustment.")

    print("[5/5] Launching TUI...")
    sleep(0.4)
    TerminalUI(rows, stats).run()
    return 0


cli = Typer(add_completion=False, no_args_is_help=False, rich_markup_mode=None)


@cli.command()
def main(
    steam_url: str | None = Option(
        None,
        "--steam-url",
        help="Steam profile URL (steamcommunity.com/id/... or /profiles/...)",
    ),
    client_id: str | None = Option(None, "--client-id", help="IGDB Client ID"),
    client_secret: str | None = Option(None, "--client-secret", help="IGDB Client Secret"),
    steam_cookie: str | None = Option(
        None,
        "--steam-cookie",
        help="Optional steamLoginSecure cookie (or full Cookie header value)",
    ),
    steam_api_key: str | None = Option(
        None,
        "--steam-api-key",
        help="Optional Steam Web API key for robust fallback",
    ),
) -> None:
    try:
        raise Exit(
            run_app(
                steam_url_arg=steam_url,
                client_id_arg=client_id,
                client_secret_arg=client_secret,
                steam_cookie_arg=steam_cookie,
                steam_api_key_arg=steam_api_key,
            ),
        )
    except KeyboardInterrupt:
        echo("\nInterrupted")
        raise Exit(130)
    except Exception as exc:
        echo(f"Error: {' '.join(wrap(str(exc), width=100))}")
        raise Exit(1)


if __name__ == "__main__":
    cli()
