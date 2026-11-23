from eval.cases import TICKET_08_CASES
from eval.runner import _prepare_case_setup


def _case_by_id(case_id: str):
    return next(case for case in TICKET_08_CASES if case.case_id == case_id)


def _assertion(case_id: str, kind: str):
    case = _case_by_id(case_id)
    return next(assertion for assertion in case.assertions if assertion.kind == kind)


def test_ticket_08_cases_distinguish_locating_from_navigation() -> None:
    locate_cart = _case_by_id("ticket08-locate-cart")
    assert any(
        assertion.kind == "url_matches" and assertion.target == r"http://localhost:4000/$"
        for assertion in locate_cart.assertions
    )
    assert _assertion("ticket08-locate-cart", "element_spotlighted").target == ('a[href="/cart"]')

    navigate_cart = _case_by_id("ticket08-navigate-cart")
    assert any(
        assertion.kind == "url_matches" and assertion.target == r"http://localhost:4000/cart$"
        for assertion in navigate_cart.assertions
    )
    assert _assertion("ticket08-navigate-cart", "element_visible").target == "h1"


def test_ticket_08_order_cases_cover_gateway_login_and_newest_order() -> None:
    locate_orders = _case_by_id("ticket08-locate-orders")
    assert locate_orders.expected_status == "complete"
    assert _assertion("ticket08-locate-orders", "element_spotlighted").target == (
        'a[href="/account"]'
    )

    logged_out = _case_by_id("ticket08-orders-logged-out")
    assert logged_out.expected_status == "question"
    assert logged_out.setup is None
    assert any(
        assertion.kind == "url_matches" and assertion.target == r"/login\?next=%2Faccount%2Forders$"
        for assertion in logged_out.assertions
    )
    assert any(
        assertion.kind == "panel_text" and assertion.target == "#pending-question p"
        for assertion in logged_out.assertions
    )

    authenticated = _case_by_id("ticket08-orders-authenticated")
    assert authenticated.setup == "authenticated"
    assert any(
        assertion.kind == "url_matches" and assertion.target == r"/account/orders$"
        for assertion in authenticated.assertions
    )
    assert (
        _assertion("ticket08-orders-authenticated", "element_spotlighted").target
        == 'a[href="#order-1003"]'
    )


class _FakeResponse:
    status = 303
    headers = {"location": "/account/orders"}


class _FakeBootstrapResponse:
    status = 200

    def json(self):
        return {"csrf": "fixture-csrf"}


class _FakeRequest:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.bootstrap_urls: list[str] = []

    def get(self, url: str) -> _FakeBootstrapResponse:
        self.bootstrap_urls.append(url)
        return _FakeBootstrapResponse()

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append((url, kwargs))
        return _FakeResponse()


class _FakeContext:
    def __init__(self) -> None:
        self.request = _FakeRequest()


def test_authenticated_case_setup_uses_only_test_login_and_does_not_return_values() -> None:
    context = _FakeContext()

    result = _prepare_case_setup(context, _case_by_id("ticket08-orders-authenticated"), 1234)

    assert result is None
    assert context.request.bootstrap_urls == ["http://localhost:4000/__shopper"]
    assert len(context.request.calls) == 1
    url, kwargs = context.request.calls[0]
    assert url == "http://localhost:4000/login"
    assert kwargs["timeout"] == 1234
    assert kwargs["max_redirects"] == 0
    assert kwargs["headers"] == {"origin": "http://localhost:4000", "x-csrf-token": "fixture-csrf"}
    assert kwargs["form"] == {
        "username": "ticket08-shopper@example.test",
        "password": "ticket08-fictional-password",
    }
