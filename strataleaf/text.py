"""Full-text tokenization and the current-head postings projection.

Stable tokenization rules:
- each CJK unified ideograph is a token of its own;
- every other maximal run of Unicode letters/digits is one token, case-folded;
- all remaining characters are separators.
A text match requires every distinct query token to appear in the field value;
repeated tokens and token positions do not affect matching.
"""
from .codec import MISSING, field
from .errors import InvalidDocument

MAX_QUERY_TERMS = 32


def is_ideograph(char):
    return "㐀" <= char <= "䶿" or "一" <= char <= "鿿" or "豈" <= char <= "﫿"


def tokenize(text):
    tokens, buffer = [], []
    for char in text:
        if is_ideograph(char):
            if buffer:
                tokens.append("".join(buffer).casefold())
                buffer = []
            tokens.append(char)
        elif char.isalnum():
            buffer.append(char)
        elif buffer:
            tokens.append("".join(buffer).casefold())
            buffer = []
    if buffer:
        tokens.append("".join(buffer).casefold())
    return tokens


def term_frequencies(text):
    counts = {}
    for token in tokenize(text):
        counts[token] = counts.get(token, 0) + 1
    return counts


def query_tokens(query):
    if not isinstance(query, str):
        raise InvalidDocument("text query must be a string")
    tokens = []
    for token in tokenize(query):
        if token not in tokens:
            tokens.append(token)
    if not tokens:
        raise InvalidDocument("text query has no searchable tokens")
    if len(tokens) > MAX_QUERY_TERMS:
        raise InvalidDocument("text query exceeds 32 distinct tokens")
    return tokens


def text_match(value, tokens):
    if not isinstance(value, str):
        return False
    present = set(tokenize(value))
    return all(token in present for token in tokens)


def refresh_postings(connection, collection, key, document):
    connection.execute("DELETE FROM text_postings WHERE collection=? AND key=?", (collection, key))
    if document is None:
        return
    for definition in connection.execute("SELECT * FROM text_defs WHERE collection=?", (collection,)).fetchall():
        value = field(document, definition["field"])
        if not isinstance(value, str):
            continue
        for token, frequency in term_frequencies(value).items():
            connection.execute("INSERT INTO text_postings VALUES (?,?,?,?,?)",
                               (collection, definition["name"], token, key, frequency))


def text_candidates(connection, collection, path, query):
    definition = connection.execute("SELECT name FROM text_defs WHERE collection=? AND field=? ORDER BY name LIMIT 1",
                                    (collection, path)).fetchone()
    if definition is None:
        return None
    keys = None
    for token in query_tokens(query):
        rows = {row[0] for row in connection.execute("SELECT key FROM text_postings WHERE collection=? AND name=? AND token=?",
                                                     (collection, definition[0], token))}
        keys = rows if keys is None else keys & rows
        if not keys:
            break
    return definition[0], keys or set()
