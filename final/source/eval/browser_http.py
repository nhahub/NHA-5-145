"""Authenticated fixture requests sharing the real shopper browser cookie jar."""

from urllib.parse import urlsplit

PANEL = "http://localhost:4100"
STORE = "http://localhost:4000"
AGENT = "http://localhost:8000"


def browser_post(context, url: str, **kwargs):
    request = context.request
    origin = f"{urlsplit(url).scheme}://{urlsplit(url).netloc}"
    if origin == STORE:
        csrf = request.get(STORE + "/__shopper").json()["csrf"]
    elif origin == AGENT:
        csrf = request.post(AGENT + "/shopper/bootstrap", headers={"origin": PANEL}).json()["csrf"]
        headers = {"origin": PANEL, "x-csrf-token": csrf}
        challenge = request.post(AGENT + "/shopper/challenge", headers=headers).json()["challenge"]
        store_csrf = request.get(STORE + "/__shopper").json()["csrf"]
        ticket = request.post(
            STORE + "/__copilot/link-ticket",
            headers={"origin": STORE, "x-csrf-token": store_csrf},
            data={"challenge": challenge, "audience": PANEL},
        ).json()["ticket"]
        linked = request.post(
            AGENT + "/shopper/link",
            headers=headers,
            data={"challenge": challenge, "ticket": ticket},
        )
        assert linked.status == 200
        origin = PANEL
    else:
        raise ValueError("Fixture destination is not an approved local service")
    headers = {**kwargs.pop("headers", {}), "origin": origin, "x-csrf-token": csrf}
    return request.post(url, headers=headers, **kwargs)
